"""Map saver output checks, including overwrites and invalid results."""

import pytest

from hamals_map_tools.map_files import verify_saved_map


def test_new_files_and_overwrite(tmp_path):
    prefix = tmp_path / 'default'
    yaml_file = prefix.with_suffix('.yaml')
    pgm_file = prefix.with_suffix('.pgm')
    old = {yaml_file: None, pgm_file: None}
    yaml_file.write_text('image: default.pgm\n', encoding='utf-8')
    pgm_file.write_bytes(b'P5\n1 1\n255\n\0')
    verify_saved_map(prefix, old)

    old = {path: path.stat().st_mtime_ns for path in (yaml_file, pgm_file)}
    yaml_file.write_text(
        'image: default.pgm\nresolution: 0.05\n', encoding='utf-8')
    pgm_file.write_bytes(b'P5\n2 1\n255\n\0\0')
    for path in (yaml_file, pgm_file):
        path.touch()
    verify_saved_map(prefix, old)


def test_missing_or_stale_or_wrong_image(tmp_path):
    prefix = tmp_path / 'default'
    yaml_file = prefix.with_suffix('.yaml')
    pgm_file = prefix.with_suffix('.pgm')
    old = {yaml_file: None, pgm_file: None}
    with pytest.raises(RuntimeError, match='bulunamadı'):
        verify_saved_map(prefix, old)
    yaml_file.write_text('image: other.pgm\n', encoding='utf-8')
    pgm_file.write_bytes(b'P5')
    with pytest.raises(RuntimeError, match='default.pgm'):
        verify_saved_map(prefix, old)
    yaml_file.write_text('image: default.pgm\n', encoding='utf-8')
    old = {path: path.stat().st_mtime_ns for path in (yaml_file, pgm_file)}
    with pytest.raises(RuntimeError, match='güncellenmedi'):
        verify_saved_map(prefix, old)
