"""seed database with notes and markov chains"""

from model import db, connect_to_db, Note, NextNote, Tempo, Chain, Tune, Instrument
import os
from music21 import note, corpus, converter
from music21.metadata import Metadata
from datetime import datetime
from sqlalchemy.orm.exc import NoResultFound

# the id of the null_note
global null_note

def get_nullnote_id():
    """make a null note for markov chains without an ending"""

    try: 
        null_note = Note.query.filter_by(duration=None).one()
    except NoResultFound: 
        null_note = Note()
        db.session.add(null_note)
        db.session.commit()

    return null_note

def get_timestamp_string():
    """simple function to return 'now' in the form of a timestamp string"""

    return datetime.now().strftime("%s")

DATADIR = 'data'
LOGDIR = 'logs'
LOGFILE = os.path.join(LOGDIR, get_timestamp_string() + '.log')
BACH_DATADIR = os.path.join(DATADIR, 'bach_cello_suites')
BACH_LOGFILE = os.path.join(BACH_DATADIR, LOGFILE)
RYAN_DATADIR = os.path.join(DATADIR, 'ryans_mammoth')
RYAN_LOGFILE = os.path.join(RYAN_DATADIR, LOGFILE)
MIDI_EXT = 'mid'

def write_logfile(logline, logfile):
    """write string to logfile, followed by a newline. Also print to terminal.

    if line is in the form of a list, join it with spaces before printing."""

    if isinstance(logline, list):
        logline = ' '.join(logline)

    print logline
    logfile.write(logline + '\n')

def markovify_score(filepath, score, logfile, default_instrument, notecount, markovcount):
    """add markov chains to db using music21 objects"""

    part_notes = score.notesAndRests

    # if the score has no notes, bail
    if not len(part_notes):
        # we're screwed. Moving on. 
        write_logfile(['\n\t****** SKIPPING', filepath, ': no notes\n'], logfile)
        return notecount, markovcount

    # get / make the tempo, tune and instrument objects
    tempo = Tempo.add(score)
    instrument = Instrument.add(score.getInstrument(), default_instrument)
    tune = Tune.add(filepath, tempo, instrument)

    write_logfile(["\ttotal notes and rests", str(len(part_notes))], logfile)

    # get the first two notes in preparation for markovification
    note_a = Note.add(part_notes[0], tune, 0)
    note_b = Note.add(part_notes[1], tune, 1)

    # let the markovification begin!
    for index, part_note in enumerate(part_notes[2:]):

        # skip zero duration notes
        if part_note.duration.quarterLength == 0:
            continue

        # make the chain
        markov = Chain.add(note_a, note_b)

        # add the note to the db and add it to the chain
        note_c = Note.add(part_note, tune, index + 2)
        NextNote.add(markov, note_c)

        # move forward one
        (note_a, note_b) = (note_b, note_c)
        db.session.flush()

        # so we make new objects to add, rather than changing existing ones
        del markov, note_c 

    # register the last markov chain
    markov = Chain.add(note_a, note_b)
    note_c = null_note
    NextNote.add(markov, note_c)

    db.session.commit()

    new_notecount = Note.query.count()
    new_markovcount = Chain.query.count()

    write_logfile(['\tadded', str(new_notecount - notecount), 'notes'], logfile)
    write_logfile(['\tadded', str(new_markovcount - markovcount), 'chains'], logfile)

    return new_notecount, new_markovcount


def load_data(use_corpus, source, logfile_path, default_instrument, ext=None, flatten=False):
    """load data from files in the data directory, or from the m21 corpus

    if it's corpus, the corpus parameter will be True, data on disk, it will be false

    if it's corpus, the source will be the corpus composer, otherwise it will
    be the location of the files within the data directory

    ext is the required file extension for files on disk

    flatten is whether or not the score requires flattening before processing"""

    notecount = Note.query.count()
    markovcount = Chain.query.count()

    logfile = open(logfile_path, 'w')

    if use_corpus: 
        paths = corpus.getComposer(source)
    else:
        paths = [os.path.join(source, file) for file in os.listdir(source)]

    for filepath in paths:

        # check for extension if necessary
        if not ext or filepath.endswith(ext): 

            write_logfile('processing {}'.format(filepath), logfile)
            score = converter.parse(filepath)
            if flatten:
                score = score.flat
            else:

                # for now, only look at first (nonempty) part to the score (parts are like 
                # parallel voices -- choral voices, for example, or for tracking double 
                # stops on the cello). In the future...?

                ### this next part iterates thorugh all parts to try and get one with notes
                # part_notes = score.parts[0].notesAndRests
                # i = 1
                # while not len(part_notes) and i < len(score.parts):
                #     part_notes = score.parts[i].notesAndRests

                score = score.parts[0]

            notecount, markovcount = markovify_score(filepath, 
                                                     score, 
                                                     logfile, 
                                                     default_instrument, 
                                                     notecount, 
                                                     markovcount)

    logfile.close()


if __name__ == "__main__":

    from flask import Flask
    app = Flask(__name__)
    connect_to_db(app)

    db.drop_all()
    db.create_all()

    # set the global nullnote ID
    null_note = get_nullnote_id()

    # midi bach files in BACH_DATADIR
    # These files were downloaded from: 
    #     http://www.jsbach.net/midi/midi_solo_cello.html"""
    load_data(use_corpus=False, 
        source=BACH_DATADIR, 
        logfile_path=BACH_LOGFILE, 
        default_instrument='Violoncello',
        ext=MIDI_EXT)

    # reels and hornpipes from the corpus
    load_data(use_corpus=True, 
        source='ryansMammoth', 
        logfile_path=RYAN_LOGFILE,
        default_instrument='Whistle',
        flatten=True)