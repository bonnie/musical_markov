"""Make compositions from musical markov chains"""

from model import db, connect_to_db, Chain, NextNote, Note
from music21 import stream
from sqlalchemy.orm.exc import NoResultFound
from seed import get_timestamp_string
from music21.midi.translate import music21ObjectToMidiFile

import random
import os

MIDI_DIR = 'data/markov_midis'

def get_common_m21_instrument(note1_id, note2_id):
    """find a common instrument between two notes

    If there's more than one common instrument, return one at random"""

    inst_sets = [set(), set()]
    for i, note in enumerate([note1_id, note2_id]):
        insts = inst_sets[i]
        tunes = Note.query.get(note).tunes
        for tune in tunes: 
            insts.add(tune.instrument)
        
        print inst_sets

    # there may be several common instruments; choose one at random
    common_instrument = (inst_sets[0] & inst_sets[1]).pop()

    return common_instrument.generate_m21()

def make_markov():
    """make a midi melody file based on database markov chain"""

    # to hold our melody in the form of a m21 score
    markov_score = stream.Score()
    part = stream.Part()

    # choose a random chain to start
    rand_markov = random.randint(1, Chain.query.count())
    chain = Chain.query.get(rand_markov)

    # start with the first two notes
    note1, note2 = chain.note1_id, chain.note2_id

    # set the instrument to be the instrument in common for the first and second notes
    m21_instrument = get_common_m21_instrument(note1, note2)
    part.insert(m21_instrument)

    # add the notes to the part
    for starter_note in (note1, note2):
        m21_note = Note.query.get(starter_note).generate_m21()
        part.append(m21_note)


    # keep on chaining until told otherwise
    while True:

        query = db.session.query(NextNote.note_id, NextNote.weight)
        query = query.filter(NextNote.chain_id == chain.chain_id)
        note_choices = query.all()

        # no chains? we're done! 
        if not note_choices:
            print "no options for this chain. Done."
            break

        # this next bit is adapted from https://docs.python.org/3/library/random.html
        # make a list with the weighted choices all spelled out. Probably not 
        # the most efficient way to do this... TODO: make more efficient
        weighted_choices = [note for note, weight in note_choices for i in range(weight)]
        next_note = random.choice(weighted_choices)
        ## end adaptation from python random docs

        # if we've hit a long rest, call it a day
        next_note_complete = Note.query.get(next_note)
        next_name = next_note_complete.note_name
        next_duration = next_note_complete.duration

        if not next_name and not next_duration:
            # we came to the end of a tune
            print "Found the end of a tune. Done."
            break

        # okay, there's an actual duration, let's get the quarter notes
        next_duration = next_duration.quarter_notes

        if next_name is None and next_duration >= 4:
            print "Found long rest. Done."
            break

        # ending on whole notes is cool too
        if next_duration >= 4:
            print "ending on a whole note"
            break

        # make a music21 note and add to the running stream
        m21_note = next_note_complete.generate_m21()
        part.append(m21_note)
        print "added note id", next_note

        # reset for next time
        note1, note2 = note2, next_note

        try: 
            chain = Chain.query.filter_by(note1_id=note1, note2_id=note2).one()
        except NoResultFound:
            # we've come to the end of the road.
            print "no chains found for last two notes. Done."
            break

    # midi-ify the stream and write to disk
    timestamp = get_timestamp_string()
    filename = timestamp + '.midi'
    filepath = os.path.join(MIDI_DIR, filename)
    markov_score.insert(0, part)
    markov_score.write('midi', fp=filepath)


if __name__ == '__main__':

    from flask import Flask
    app = Flask(__name__)
    connect_to_db(app)

    make_markov()