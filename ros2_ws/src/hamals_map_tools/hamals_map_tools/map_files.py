"""Validate the files produced by Nav2's map saver."""


def verify_saved_map(prefix, previous):
    """Require fresh files with the expected image reference."""
    yaml_file = prefix.with_suffix('.yaml')
    pgm_file = prefix.with_suffix('.pgm')
    for path in (yaml_file, pgm_file):
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(
                f'Kaydedilen dosya bulunamadı veya boş: {path}')
        if previous[path] == path.stat().st_mtime_ns:
            raise RuntimeError(f'Kaydedilen dosya güncellenmedi: {path}')
    lines = yaml_file.read_text(encoding='utf-8').splitlines()
    image_lines = [line.partition(':')[2].strip().strip('"\'')
                   for line in lines
                   if line.partition(':')[0].strip() == 'image']
    if image_lines != ['default.pgm']:
        raise RuntimeError(
            'Harita YAML dosyası default.pgm dosyasına işaret etmiyor.')
