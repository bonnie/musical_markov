"""data model for music markov chains"""

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm.exc import NoResultFound
from fractions import Fraction
import music21 as m21

# This is the connection to the PostgreSQL database; we're getting this through
# the Flask-SQLAlchemy helper library. On this, we can find the `session`
# object, where we do most of our interactions (like committing, etc.)

db = SQLAlchemy()


##############################################################################
# Model definitions

class Music21AnalogMixin():
    """a mixin class for translating between my objs and m21 objs"""

    @classmethod
    def add(cls, **kwargs):
        """given data (kwargs), find obj or instantiate obj and add to db. 

        return obj"""

        try:
            new_obj = cls.query.filter_by(**kwargs).one()
        except NoResultFound:
            new_obj = cls(**kwargs)
            db.session.add(new_obj)

        return new_obj

class Duration(db.Model, Music21AnalogMixin):
    """note duration"""

    __tablename__ = 'durations'

    duration_id = db.Column(db.Integer, autoincrement=True, primary_key=True)

    # this is in number of quarter notes (e.g. an eighth note would be 0.5)
    quarter_notes = db.Column(db.Float, nullable=False)

    @classmethod
    def add(cls, quarter_notes):
        """given length in quarter notes, instantiate a duration and add to db 

        Will just return existing duration object if it's already there

        returns duration obj"""

        # translate fraction to float
        if isinstance(quarter_notes, Fraction):
            quarter_notes = float(quarter_notes)

        # instantiate / find obj and return
        return super(Duration, cls).add(quarter_notes=quarter_notes)

    def generate_m21(self):
        """return a music21 duration object for this duration"""

        return m21.duration.Duration(self.quarter_notes)

    def __repr__(self):
        """Provide helpful representation when printed."""

        return "<Duration duration_id=%s quarter_notes=%s>" % \
                (self.duration_id, self.quarter_notes)


class Note(db.Model, Music21AnalogMixin):
    """Note, including pitch and duration"""

    __tablename__ = 'notes'

    note_id = db.Column(db.Integer, autoincrement=True, primary_key=True)

    # pitch; will be null for a rest
    note_name = db.Column(db.String(3), nullable=True)
    octave = db.Column(db.Integer, nullable=True)

    duration_id = db.Column(db.Integer, db.ForeignKey('durations.duration_id'))
    tempo_id = db.Column(db.Integer, db.ForeignKey('tempi.tempo_id'))

    ## relationships ##
    duration = db.relationship('Duration')
    tempo = db.relationship('Tempo')

    @classmethod
    def add(cls, m21_note, tune, index):
        """create note given a music21 note object, a tune obj, and an index 

        Also, add note to tune. 

        If note already exists, don't create a new one, just add it to the tune

        Returns note object
        """

        # create a duration if necessary
        duration = Duration.add(m21_note.duration.quarterLength)

        try:
            pitch = m21_note.pitch
            note_name = pitch.name
            octave = pitch.octave
        except AttributeError:
            # rests have no name or octave, so it must be a rest
            note_name = None
            octave = None

        # instantiate / find obj and return
        new_note = super(Note, cls).add(note_name=note_name, 
                                  octave=octave, 
                                  duration_id=duration.duration_id)

        # add note to tune
        db.session.flush()
        tunenote = TuneNote(tune_id=tune.tune_id, note_id=new_note.note_id, index=index)

        return new_note


    def generate_m21(self):
        """return a music21 note object for this note. 

        for creating streams to transform into MIDI files"""

        if self.note_name:
            # it's a note
            mnote = m21.note.Note(self.note_name + str(self.octave))

        else:
            # it's a rest
            mnote = m21.note.Rest()

        mnote.duration = self.duration.generate_m21()
        return mnote

    def __repr__(self):
        """Provide helpful representation when printed."""

        return "<Note note_id=%s note_name=%s octave=%s quarter notes=%s>" % \
                (self.note_id, self.note_name, self.octave, self.duration.quarter_notes)


class Tempo(db.Model, Music21AnalogMixin):
    """musical tempo"""

    __tablename__ = 'tempi'

    tempo_id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    text = db.Column(db.String(32), nullable=True)
    seconds_per_quarter = db.Column(db.Float, nullable=False)

    @classmethod
    def add(cls, m21_score):
        """given a music21 score obj, instantiate a tempo and add to db 

        Will just return existing tempo object if it's already there

        returns tempo obj"""

        # the [0] means we're just taking the first tempo of the score
        metronome_mark =  m21_score.metronomeMarkBoundaries()[0][2]
        spq = metronome_mark.secondsPerQuarter()
        text = metronome_mark.text

        # instantiate / find obj and return
        return super(Tempo, cls).add(text=text, seconds_per_quarter=spq)


    def __repr__(self):
        """Provide helpful representation when printed."""

        return "<Tempo id=%s text=%s seconds/quarter=%s>" % \
                (self.tempo_id, self.text, self.seconds_per_quarter)


class Instrument(db.Model, Music21AnalogMixin):
    """to hold midi instruments"""

    __tablename__ = 'instruments'

    instrument_id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    instrument_name = db.Column(db.String(32))

    @classmethod
    def add(cls, m21_instrument):
        """given a music21 instrument, instantiate and add this instrument

        If instrument already exists, simply return existing instrument

        returns instrument obj
        """

        # instantiate / find obj and return
        return super(Instrument, cls).add(instrument_name=m21_instrument.instrumentName)


    def generate_m21(self):
        """return a music21 instrument object for this instrument"""

        return m21.instrument.fromString(self.instrument_name)

    def __repr__(self):
        """Provide helpful representation when printed."""

        return "<Instrument instrument_id=%s instrument_name=%s>" % \
                (self.instrument_id, self.instrument_id)


class TuneNote(db.Model):
    """associating tunes with notes"""

    __tablename__ = 'tunenotes'
    
    tunenote_id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    tune_id = db.Column(db.Integer, db.ForeignKey('tunes.tune_id'))
    note_id = db.Column(db.Integer, db.ForeignKey('notes.note_id'))

    # what number is this in the tune, starting with 0
    index = db.Column(db.Integer)

    def __repr__(self):
        """Provide helpful representation when printed."""

        return "<TuneNote tunenote_id=%s tune_id=%s note_id=%s>" % \
                (self.tunenote_id, self.tune_id, self.note_id)


class Tune(db.Model):
    """A tune containing notes"""

    __tablename__ = 'tunes'

    tune_id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    tune_name = db.Column(db.String(256))
    tempo_id = db.Column(db.Integer, db.ForeignKey('tempi.tempo_id'))
    instrument_id = db.Column(db.Integer, db.ForeignKey('instruments.instrument_id'))

    ### relationships ###
    tempo = db.relationship('Tempo')
    instrument = db.relationship('Instrument')
    notes = db.relationship('Note', 
                            secondary='tunenotes', 
                            order_by='TuneNote.index', 
                            backref='tunes')

    @classmethod
    def add(cls, name, tempo, instrument):
        """given a name and a tempo, create a tune obj and add to db 

        returns tune obj"""

        # no 'super' method here -- no such thing as a duplicate tune (for now...)
        tune = cls(tune_name=name, 
                   tempo_id=tempo.tempo_id, 
                   instrument_id=instrument.instrument_id)
        return tune

    def __repr__(self):
        """Provide helpful representation when printed."""

        return "<Tune tune_id=%s name=%s tempo_id=%s>" % \
                (self.tune_id, self.name, self.tempo_id)

    
class Chain(db.Model, Music21AnalogMixin):
    """table to track Markov sequences"""

    __tablename__ = 'chains'

    chain_id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    note1_id = db.Column(db.Integer, db.ForeignKey('notes.note_id'))
    note2_id = db.Column(db.Integer, db.ForeignKey('notes.note_id'))

    @classmethod
    def add(cls, note1, note2):
        """given two note objects, instantiate a chain (or return existing chain)

        returns a chain object.
        """
        
        # instantiate / find obj and return
        return super(Chain, cls).add(note1_id=note1.note_id, note2_id=note2.note_id)


    def __repr__(self):
        """Provide helpful representation when printed."""

        return "<Chain chain_id=%s notes=%s, %s>" % \
                (self.chain_id, self.note1_id, self.note2_id)

class NextNote(db.Model):
    """track the next note possibilities for each Markov sequence"""

    __tablename__ = 'nextnote'

    nextnote_id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    chain_id = db.Column(db.Integer, db.ForeignKey('chains.chain_id'))
    note_id = db.Column(db.Integer, db.ForeignKey('notes.note_id'))
    weight = db.Column(db.Integer, default=1)

    @classmethod
    def add(cls, chain, note):
        """given a chain obj and a note obj, instantiate a nextnote object

        OR: add to the weight of the nextnote object if it already exists
        """

        # no super method here -- we need to add to the weight if we find the nextnote
        try:
            nextnote = cls.query.filter_by(chain_id=chain.chain_id, note_id=note.note_id).one()

            # if we got this far, it exists; add to weight
            nextnote.weight = nextnote.weight + 1

        except NoResultFound:
            # doesn't exist; make a new one
            nextnote = cls(chain_id=chain.chain_id, note_id=note.note_id)


        db.session.add(nextnote)
        return nextnote


    def __repr__(self):
        """Provide helpful representation when printed."""

        return "<NextNote nextnote_id=%s chain_id=%s, note_id=%s, weight=%s>" % \
                (self.nextnote_id, self.chain_id, self.note_id, self.weight)


##############################################################################
# Helper functions

def connect_to_db(app):
    """Connect the database to our Flask app."""

    # Configure to use our PostgreSQL database
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql:///musicalmarkov'
#    app.config['SQLALCHEMY_ECHO'] = True
    db.app = app
    db.init_app(app)


if __name__ == "__main__":
    # As a convenience, if we run this module interactively, it will leave
    # you in a state of being able to work with the database directly.

    from flask import Flask
    app = Flask(__name__)
    connect_to_db(app)

    # db.drop_all()
    db.create_all()

    print "Connected to DB."
