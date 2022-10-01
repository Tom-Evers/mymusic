import os
import re
from os import rename, listdir
from os.path import splitext, join, isdir
from typing import Optional, List

from thefuzz import fuzz

from eutils.eutils import yes_no, pick_from_list, start

music_sources = "C:\\Users\\tom_e\\Music\\DnB\\Mixtape sources"
re_parentheses_info = re.compile(r"(?<=[\s*])\(.+\)")
re_bracket_info = re.compile(r"(?<=[\s*])\[.+]")


def rename_file(file: str) -> str:
    filename, extension = splitext(file)
    print(f"Wrong format: {filename}")

    confirmed = False
    while not confirmed:
        accepted = False
        while not accepted:
            filename = input("Enter new name:")
            accepted = yes_no(f"Accept name '{filename}'?", default=True)

        confirmed = yes_no(f'Confirm rename "{file}" to "{filename + extension}"')

    rename(join(music_sources, file),
           join(music_sources, filename + extension))
    return filename + extension


def filename_incorrect(filename: str) -> bool:
    # A filename needs to be of the format
    # "Key - Artists - Title (Version) [Notes]"
    # With (Version) and [Notes] being optional

    if len(filename.split(' - ')) != 3:
        return True

    number_of_versions = len(re_parentheses_info.findall(filename))
    if number_of_versions > 1:
        return True

    number_of_notes = len(re_bracket_info.findall(filename))
    if number_of_notes > 1:
        return True

    notes = re_bracket_info.search(filename)
    if notes is not None and notes.end() != len(filename):
        return True

    version_info = re_parentheses_info.search(filename)
    if version_info is not None and ((notes is not None and version_info.end() != notes.start() - 1) or
                                     (notes is None and version_info.end() != len(filename))):
        return True

    return False


class SongFile:
    def __init__(self, filename: str):
        global re_parentheses_info, re_bracket_info

        file, extension = splitext(filename)

        # If the filename doesn't make sense at all, let me rename it before continuing
        while filename_incorrect(file):
            filename = rename_file(filename)
            file, extension = splitext(filename)

        self.file_types = [{'path': os.path.join(music_sources, filename), 'extension': extension}]

        key, artists, title_and_info = file.split(' - ')
        self.key = key.lstrip().rstrip()
        self.artists = artists.lstrip().rstrip()
        self.version = ""
        self.notes = ""

        version = re_parentheses_info.search(title_and_info)
        if version is not None:
            version = version[0]
            self.version = version.lstrip('(').rstrip(')')
            title_and_info = title_and_info.replace(version, '')

        notes = re_bracket_info.search(title_and_info)
        if notes is not None:
            notes = notes[0]
            self.notes = notes.lstrip('[').rstrip(']')
            title_and_info = title_and_info.replace(notes, '')

        self.title = title_and_info.lstrip().rstrip()
        self.correct_filenames()

    def correct_filenames(self) -> None:
        filename = self.filename_base()
        for file_type in self.file_types:
            old_path = file_type['path']
            correct_path = os.path.join(music_sources, filename + file_type['extension'])
            if correct_path != old_path and yes_no(f'Confirm rename "{os.path.split(old_path)[1]}" to "{filename}"', default=True):
                rename(old_path, correct_path)
                file_type['path'] = correct_path

    def filename_base(self) -> str:
        filename = f"{self.key} - {self}"
        if self.version != "":
            filename += f" ({self.version})"
        if self.notes != "":
            filename += f" [{self.notes}]"
        return filename

    def match(self, song_file: 'SongFile') -> Optional[bool]:
        if self.artists != song_file.artists or self.title != song_file.title:
            assert not "Don't try to match versions of different songs"
            return None

        if self.version == song_file.version and self.notes == song_file.notes:
            # The key might still differ!
            return True

        version_ratio = fuzz.ratio(self.version, song_file.version)
        notes_ratio = fuzz.ratio(self.notes, song_file.notes)
        if 100 >= version_ratio > 80 and 100 >= notes_ratio > 80:
            return False

        return None

    def append(self, song_file: 'SongFile') -> bool:
        if self.key != song_file.key:
            if yes_no("Key mismatch, do you want to open the files to listen to them?"):
                for file_type in self.file_types:
                    start(file_type['path'])
                for file_type in song_file.file_types:
                    start(file_type['path'])

            if not yes_no("Are these in the same key?"):
                # If these different versions are indeed keyed differently, don't append
                return False

            if pick_from_list([self, song_file], "Which one has the correct key?", return_element=False) == 0:
                song_file.key = self.key
                song_file.correct_filenames()
            else:
                self.key = song_file.key
                self.correct_filenames()

            for file_type in song_file.file_types:
                if file_type['extension'] in map(lambda i: i['extension'], self.file_types):
                    print(f'Duplicate detected: "{file_type["path"]}"')
                    assert not "Duplicates should not occur"
                    return False
                self.file_types.append(file_type)

            return True

    def __str__(self):
        return f"{self.artists} - {self.title}"


class Song:
    def __init__(self, song_file: SongFile):
        self.artists = song_file.artists
        self.title = song_file.title
        self.editions = [song_file]

    def match(self, song_file: SongFile) -> Optional[bool]:
        if self.artists == song_file.artists and self.title == song_file.title:
            return True

        artist_ratio = fuzz.ratio(self.artists, song_file.artists)
        title_ratio = fuzz.ratio(self.title, song_file.title)
        if 100 >= artist_ratio > 80 and 100 >= title_ratio > 80:
            return False

        return None

    def append(self, song_file: SongFile):
        # Check if this edition already exists
        approximate_matches: List[SongFile] = []
        exact_match: Optional[SongFile] = None
        for edition in self.editions:
            match edition.match(song_file):
                case True:
                    exact_match = edition
                    break
                case False:
                    approximate_matches.append(edition)
                case None:
                    pass

        if exact_match is None:
            chosen_match_index = pick_from_list(["No matches"] + [e.version + (f" ({e.notes})" if e.notes != "" else "") + f" ({e.key})"
                                                                  for e in approximate_matches],
                                                f"Pick a match for {song_file.filename_base()}", return_element=False)
            if chosen_match_index != 0:
                exact_match = approximate_matches[chosen_match_index - 1]

        if exact_match is not None:
            exact_match.append(song_file)
        else:
            self.editions.append(song_file)

    def __str__(self):
        return f"{self.artists} - {self.title}"


def analyse() -> List[Song]:
    collection: List[Song] = []
    for filename in listdir(music_sources):
        if isdir(join(music_sources, filename)):
            continue

        song_file = SongFile(filename)

        # Check if we already have another version of this song in our collection
        approximate_matches = []
        exact_match: Optional[Song] = None
        for song in collection:
            match song.match(song_file):
                case True:
                    exact_match = song
                    break
                case False:
                    approximate_matches.append(song)
                case None:
                    pass

        # If there are no exact matches, pick from approximate matches (defaults to None if there are none)
        if exact_match is None:
            chosen_match = pick_from_list(["No matches"] + list(map(str, approximate_matches)),
                                          f'"Pick a match for "{song_file}"',
                                          return_element=False,
                                          auto_return_single_element=True)
            if chosen_match != 0:
                exact_match = approximate_matches[chosen_match - 1]

        if exact_match is not None:
            exact_match.append(song_file)
        else:
            collection.append(Song(song_file))

    return collection


if __name__ == '__main__':
    _collection = analyse()

# if __name__ == '__main__':
#     _collection = {}
#     for _file in listdir(music_sources):
#         if not isdir(join(music_sources, _file)):
#             _metadata = parse_filename(_file)
#             _artists = _metadata['artists']
#             _title = _metadata['title']
#             _edition = {'version': _metadata['version'],
#                         'notes': _metadata['notes'],
#                         'formats': [_metadata['format']]}
#             _filename = _metadata['filename']
#
#             _exact_match, _close_matches = try_match(_collection, _artists, _title)
#             _chosen_match = None
#             if _exact_match is not None:
#                 _chosen_match = _exact_match
#             elif len(_close_matches) > 0:
#                 print(f"Processing {_file}")
#                 _match_index = eutils.eutils.pick_from_list(["No matches"] + _close_matches, return_element=False)
#                 if _match_index > 0:
#                     _chosen_match = _close_matches[_match_index - 1]
#                     _rename_choice = eutils.eutils.pick_from_list(
#                         [f"{_chosen_match['artists']} - {_chosen_match['title']}",
#                          f"{_artists} - {_title}"],
#                         prompt="Choose the correct title:",
#                         return_element=False)
#
#                     if _rename_choice == 1:
#                         _chosen_match['artists'] = _artists
#                         _chosen_match['title'] = _title
#                         for i, _chosen_edition in enumerate(_chosen_match['editions']):
#                             new_filename = f"{_chosen_match['key']} - {_chosen_match['artists']} - {_chosen_match['title']}"
#                             if _chosen_edition['version'] != "Original Mix":
#                                 new_filename += f" ({_chosen_edition['version']})"
#                             if len(_chosen_edition['notes']) > 0:
#                                 new_filename += f" [{_chosen_edition['notes']}]"
#                             for ext in _chosen_edition['formats']:
#                                 pass  # TODO: Check
#                                 # try:
#                                 #     rename(os.path.join(music_sources, f"{_chosen_file}.{ext}"),
#                                 #            os.path.join(music_sources, new_filename))
#                                 # except Exception as e:
#                                 #     print(f"Could not rename {_chosen_file} to {new_filename}")
#                                 #     print(e)
#                     else:
#                         assert _rename_choice == 0
#                         _artists = _chosen_match['artists']
#                         _title = _chosen_match['title']
#                         new_filename = f"{_chosen_match['key']} - {_artists} - {_title}"
#                         if _edition['version'] != "Original Mix":
#                             new_filename += f" ({_edition['version']})"
#                         if len(_edition['notes']) > 0:
#                             new_filename += f" [{_edition['notes']}]"
#                         new_filename += f".{_metadata['format']}"
#                         pass  # TODO: Check
#                         # try:
#                         #     rename(os.path.join(music_sources, _file),
#                         #            os.path.join(music_sources, new_filename))
#                         # except Exception as e:
#                         #     print(f"Could not rename {_file} to {new_filename}")
#                         #     print(e)
#
#             if _chosen_match is not None:
#                 _match_editions = _chosen_match['editions']
#                 if _match_editions is None:
#                     assert not "We should already have an edition if a song is found"
#                 found = False
#                 for _match_edition in _match_editions:
#                     if _match_edition['version'] == _edition['version'] and _match_edition['notes'] == _edition[
#                         'notes']:
#                         _match_edition['formats'] += _edition['formats']
#                         found = True
#                         break
#                 if not found:
#                     _match_editions.append(_edition)
#             else:
#                 _collection[(_artists, _title)] = {'key': _metadata['key'],
#                                                    'artists': _artists,
#                                                    'title': _title,
#                                                    'editions': [_edition]}
#
#     for item in _collection.values():
#         for edition in item['editions']:
#             source = f"{item['key']} - {item['artists']} - {item['title']}"
#             if edition['version'] != "Original Mix":
#                 source += f" ({edition['version']})"
#             if edition['notes'] != "":
#                 source += f" [{edition['notes']}]"
#
#             if 'mp3' in edition['formats']:
#                 source += ".mp3"
#             elif 'flac' in edition['formats']:
#                 source += ".flac"
#             else:
#                 source += f".{edition['formats'][0]}"
#
#             try:
#                 shutil.copy2(os.path.join(music_sources, source), "F:")
#             except Exception as e:
#                 print(f"Failed {source}")
