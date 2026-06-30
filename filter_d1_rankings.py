#!/usr/bin/env python3
"""Filter all ranking tables in scout HTML files to show only Division 1 teams.
Fixed version: properly separates D2 row content from subsequent inter-row content.
"""

import re
import glob
import os

D2_ABBREVIATED = {
    'Green Rock', 'Hanazono K', 'Hino Red D', 'Kamaishi S',
    'Kyushudenr', 'RedHurrica', 'Shimizu Ko', 'Toyota Ind'
}
D2_FULL_NAMES = [
    'Green Rockets Tokatsu', 'Hanazono Kintetsu Liners',
    'Hino Red Dolphins', 'Kamaishi Seawaves',
    'Kyushudenryoku KyudenVoltex', 'RedHurricanes Osaka',
    'Shimizu Koto Blue Sharks', 'Toyota Industries Shuttles Aichi',
]

COL_OPEN = '<div style="display:flex;flex-direction:column;gap:2px">'
ROW_OPEN = '<div style="display:flex;align-items:center;gap:5px'
TEAM_RE = re.compile(r'width:72px[^>]*>([^<]+)</span>')
RANK_RE = re.compile(r'>([\d]+)</span>')


def split_at_row_end(row_part):
    """Split at the closing </div> of the ranking row div.
    row_part is everything AFTER ROW_OPEN; the row div is at depth=1.
    Returns (row_content, subsequent_content).
    """
    depth = 1
    for m in re.finditer(r'</?div', row_part):
        tag = row_part[m.start():m.start() + 5]
        if tag.startswith('<div'):
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                end_pos = m.end() + 1  # include the '>' of </div>
                return row_part[:end_pos], row_part[end_pos:]
    return row_part, ''


def remove_legend_d2(content):
    for name in D2_FULL_NAMES:
        pattern = (
            r'<div style="display:flex;align-items:center;gap:4px">'
            r'<div[^>]+></div>'
            r'<span[^>]*>' + re.escape(name) + r'</span>'
            r'</div>'
        )
        content = re.sub(pattern, '', content)
    return content


def process_column_section(section):
    """Process one column container section (content after COL_OPEN).
    KEY FIX: For D2 rows in non-last positions, use split_at_row_end to
    preserve any content between the row end and the next ROW_OPEN.
    """
    row_parts = section.split(ROW_OPEN)

    if len(row_parts) <= 1:
        return section

    new_rank = 1
    output = [row_parts[0]]  # empty prefix

    # ── Middle rows (all except the very last piece) ──────────────────────
    for row_part in row_parts[1:-1]:
        team_m = TEAM_RE.search(row_part[:500])
        if not team_m:
            # Not a league ranking row — keep as-is
            output.append(ROW_OPEN + row_part)
            continue

        team = team_m.group(1)

        if team in D2_ABBREVIATED:
            # Split at the row's closing </div> so we keep any content
            # (e.g., section wrappers) that sits between this row end
            # and the next ROW_OPEN.
            _, subsequent = split_at_row_end(row_part)
            if subsequent:
                output.append(subsequent)
            # D2 row itself is discarded
        else:
            # D1 team — update rank number, keep entire piece
            new_part = RANK_RE.sub(f'>{new_rank}</span>', row_part, count=1)
            new_rank += 1
            output.append(ROW_OPEN + new_part)

    # ── Last piece (last row content + all subsequent content to next COL_OPEN) ──
    last_piece = row_parts[-1]
    team_m = TEAM_RE.search(last_piece[:500])

    if not team_m:
        # Not a ranking row — keep entire last piece as-is
        output.append(ROW_OPEN + last_piece)
    else:
        team = team_m.group(1)
        row_content, subsequent = split_at_row_end(last_piece)
        if team in D2_ABBREVIATED:
            # Discard D2 row, keep subsequent
            if subsequent:
                output.append(subsequent)
        else:
            # D1 — update rank, keep row + subsequent
            new_row = RANK_RE.sub(f'>{new_rank}</span>', row_content, count=1)
            output.append(ROW_OPEN + new_row + subsequent)

    return ''.join(output)


def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_len = len(content)

    # Step 1: Remove D2 entries from legend
    content = remove_legend_d2(content)

    # Step 2: Split by column containers and process each
    sections = content.split(COL_OPEN)
    new_sections = [sections[0]]
    for section in sections[1:]:
        new_sections.append(COL_OPEN + process_column_section(section))
    content = ''.join(new_sections)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    return original_len - len(content)


if __name__ == '__main__':
    scout_files = sorted(glob.glob('/Users/ktachikawa/Desktop/kubota-spears-analytics/scout_*.html'))
    print(f"Processing {len(scout_files)} scout files...")
    total = 0
    for fpath in scout_files:
        removed = process_file(fpath)
        print(f"  {os.path.basename(fpath)}: -{removed:,} chars")
        total += removed
    print(f"\nDone. Total removed: {total:,} chars")
