import os
import re
import shutil
from os import rename, listdir
from os.path import splitext, join, isdir
from pprint import pprint

from thefuzz import fuzz

import eutils.eutils
from eutils.eutils import *

music_sources = "C:\\Users\\tom_e\\Music\\DnB\\Mixtape sources"


def rename_file(file):
    filename, extension = splitext(file)
    print(f"Wrong format: {filename}")

    accepted = False
    while not accepted:
        filename = input("Enter new name:")
        accepted = yes_no(f"Accept name '{filename}'?", default=True)

    rename(join(music_sources, file),
           join(music_sources, filename + extension))

    return filename


re_parentheses_info = re.compile(r"(?<=[\s*])\(.+\)")
re_bracket_info = re.compile(r"(?<=[\s*])\[.+]")


def filename_incorrect(filename):
    all_par_info = re_parentheses_info.findall(filename)
    first_par_info = re_parentheses_info.search(filename)
    all_bracket_info = re_bracket_info.findall(filename)
    first_bracket_info = re_bracket_info.search(filename)
    has_par_info = first_par_info is not None
    par_info_not_at_end = has_par_info and first_par_info.end() != len(filename)
    has_bracket_info = first_bracket_info is not None
    par_info_not_before_bracket_info = has_par_info and has_bracket_info and first_par_info.end() >= first_bracket_info.start()
    bracket_info_not_at_end = has_bracket_info and first_bracket_info.end() != len(filename)
    return len(filename.split(' - ')) != 3 or \
           len(all_par_info) > 1 or \
           (has_par_info and par_info_not_at_end and par_info_not_before_bracket_info) or \
           (has_bracket_info and bracket_info_not_at_end)


def parse_filename(file):
    global re_parentheses_info, re_bracket_info
    # Simple data:
    filename, extension = splitext(file)
    metadata = {'filename': filename, 'format': extension[1:]}

    while filename_incorrect(filename):
        # Invalid filename
        filename = rename_file(file)

    # Key and artist
    key, artists, title_and_info = filename.split(' - ')
    metadata['key'] = key
    metadata['artists'] = artists

    # Title and information
    title = title_and_info

    first_info = re_parentheses_info.search(title_and_info)
    if first_info is not None:
        info = first_info[0]
        metadata['version'] = info.lstrip('(').rstrip(')')
        title = title.replace(info, '')

    first_note = re_bracket_info.search(title_and_info)
    if first_note is not None:
        note = first_note[0]
        metadata['notes'] = note.lstrip('[').rstrip(']')
        title = title.replace(note, '')

    if 'version' not in metadata:
        metadata['version'] = "Original Mix"
    if 'notes' not in metadata:
        metadata['notes'] = ""

    metadata['title'] = title.rstrip()

    # pprint(metadata)
    return metadata


def try_match(collection, artists, title):
    exact_match = None
    close_matches = []
    for item in collection.items():
        (item_artists, item_title), result = item
        artist_ratio = fuzz.ratio(item_artists, artists)
        title_ratio = fuzz.ratio(item_title, title)
        if 100 == artist_ratio and 100 == title_ratio:
            exact_match = result
            break
        if 100 >= artist_ratio > 80 and 100 >= title_ratio > 80:
            close_matches.append(result)
    return exact_match, close_matches


if __name__ == '__main__':
    _collection = {}
    for _file in listdir(music_sources):
        if not isdir(join(music_sources, _file)):
            _metadata = parse_filename(_file)
            _artists = _metadata['artists']
            _title = _metadata['title']
            _edition = (_metadata['format'], _metadata['version'], _metadata['notes'])
            _filename = _metadata['filename']

            _exact_match, _close_matches = try_match(_collection, _artists, _title)
            _chosen_match = None
            if _exact_match is not None:
                _chosen_match = _exact_match
            elif len(_close_matches) > 0:
                print(f"Processing {_file}")
                _match_index = eutils.eutils.pick_from_list(["No matches"] + _close_matches, return_element=False)
                if _match_index > 0:
                    _chosen_match = _close_matches[_match_index - 1]
                    _rename_choice = eutils.eutils.pick_from_list(
                        [f"{_chosen_match['artists']} - {_chosen_match['title']}",
                         f"{_artists} - {_title}"],
                        prompt="Choose the correct title:",
                        return_element=False)

                    FORMAT = 0
                    VERSION = 1
                    NOTES = 2
                    if _rename_choice == 1:
                        _chosen_match['artists'] = _artists
                        _chosen_match['title'] = _title
                        for i, _chosen_file in enumerate(_chosen_match['filenames']):
                            _chosen_edition = _chosen_match['editions'][i]
                            new_filename = f"{_chosen_match['key']} - {_chosen_match['artists']} - {_chosen_match['title']}"
                            if _chosen_edition[VERSION] != "Original Mix":
                                new_filename += f" ({_chosen_edition[VERSION]})"
                            if len(_chosen_edition[NOTES]) > 0:
                                new_filename += f" [{_chosen_edition[NOTES]}]"
                            new_filename += f".{_chosen_edition[FORMAT]}"
                            try:
                                rename(os.path.join(music_sources, f"{_chosen_file}.{_chosen_edition[FORMAT]}"),
                                       os.path.join(music_sources, new_filename))
                            except Exception as e:
                                print(f"Could not rename {_chosen_file} to {new_filename}")
                                print(e)
                    else:
                        assert _rename_choice == 0
                        _artists = _chosen_match['artists']
                        _title = _chosen_match['title']
                        new_filename = f"{_chosen_match['key']} - {_artists} - {_title}"
                        if _edition[VERSION] != "Original Mix":
                            new_filename += f" ({_edition[VERSION]})"
                        if len(_edition[NOTES]) > 0:
                            new_filename += f" [{_edition[NOTES]}]"
                        new_filename += f".{_edition[FORMAT]}"
                        try:
                            rename(os.path.join(music_sources, _file),
                                   os.path.join(music_sources, new_filename))
                        except Exception as e:
                            print(f"Could not rename {_file} to {new_filename}")
                            print(e)

            if _chosen_match is not None:
                _match_editions = _chosen_match['editions']
                if _match_editions is None:
                    assert not "We should already have an edition if a song is found"
                if _edition in _match_editions:
                    assert not "Duplicate found"
                else:
                    _match_editions.append(_edition)
                    _chosen_match['filenames'].append(_filename)
            else:
                _collection[(_artists, _title)] = {'key': _metadata['key'],
                                                   'artists': _artists,
                                                   'title': _title,
                                                   'editions': [_edition],
                                                   'filenames': [_filename]}

