"""seed database with notes and markov chains"""

from model import db, connect_to_db, Note, NextNote, Tempo, Chain, Tune, Instrument
import os
from music21 import note, corpus, converter
from music21.metadata import Metadata
from datetime import datetime

def get_timestamp_string():
    """simple function to return 'now' in the form of a timestamp string"""

    return datetime.now().strftime("%s")

DATADIR = 'data'
LOGDIR = 'logs'
LOGFILE = os.path.join(LOGDIR, get_timestamp_string() + '.log')
BACH_DATADIR = os.path.join(DATADIR, 'bach_cello_suites')
BACH_LOGFILE = os.path.join(BACH_DATADIR, LOGFILE)
MIDI_EXT = 'mid'

def write_logfile(logline, logfile):
    """write string to logfile, followed by a newline. Also print to terminal.

    if line is in the form of a list, join it with spaces before printing."""

    if isinstance(logline, list):
        logline = ' '.join(logline)

    print logline
    logfile.write(logline + '\n')

def markovify_score(filepath, score, logfile, notecount, markovcount):
    """add markov chains to db using music21 score object"""

    # for now, only look at first (nonempty) part to the score (parts are like 
    # parallel voices -- choral voices, for example, or for tracking double 
    # stops on the cello). In the future...?

    # if the score has no notes, bail
    part_notes = score.parts[0].notesAndRests
    i = 1
    while not len(part_notes) and i < len(score.parts):
        part_notes = score.parts[i].notesAndRests

    if not len(part_notes):
        # we're screwed. Moving on. 
        write_logfile(['\n\t****** SKIPPING', filepath, ': no notes\n'], logfile)
        return notecount, markovcount

    # get / make the tempo, tune and instrument objects
    tempo = Tempo.add(score)
    instrument = Instrument.add(score.parts[0].getInstrument())
    tune = Tune.add(filepath, tempo, instrument)

    write_logfile(["\ttotal notes and rests", str(len(part_notes))], logfile)

    # get the first two notes in preparation for markovification
    note_a = Note.add(part_notes[0], tune, 0)
    note_b = Note.add(part_notes[1], tune, 1)

    # let the markovification begin!
    for index, part_note in enumerate(part_notes[2:]):

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

    db.session.commit()

    new_notecount = Note.query.count()
    new_markovcount = Chain.query.count()

    write_logfile(['\tadded', str(new_notecount - notecount), 'notes'], logfile)
    write_logfile(['\tadded', str(new_markovcount - markovcount), 'chains'], logfile)

    return new_notecount, new_markovcount


def load_bachdata():
    """load data from midi bach files in BACH_DATADIR

    These files were downloaded from: 

        http://www.jsbach.net/midi/midi_solo_cello.html"""

    notecount = 0
    markovcount = 0
    logfile = open(BACH_LOGFILE, 'w')

    for filepath in os.listdir(BACH_DATADIR):
        if filepath.endswith(MIDI_EXT): 
            write_logfile('processing {}'.format(filepath), logfile)
            score = converter.parse(os.path.join(BACH_DATADIR, filepath))
            notecount, markovcount = markovify_score(filepath, score, logfile, notecount, markovcount)

    logfile.close()

def load_reels_and_hornpipes():
    """load data from the music21 corpus Ryan's Mammoth Collection"""

    pass


if __name__ == "__main__":

    from flask import Flask
    app = Flask(__name__)
    connect_to_db(app)

    db.drop_all()
    db.create_all()

    load_bachdata()