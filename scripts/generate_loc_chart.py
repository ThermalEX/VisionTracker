"""
Generate Lines of Code chart from git history.
Excludes app/siui/ (external UI framework) to show only core code.

Usage:
    python scripts/generate_loc_chart.py
"""

import subprocess
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from pathlib import Path
import re


def get_loc_history():
    """Get LOC for each commit, excluding siui/ directory."""
    # Get all commits
    result = subprocess.run(
        ['git', 'log', '--format=%H %as %s', '--reverse'],
        capture_output=True, text=True, encoding='utf-8'
    )

    commits = []
    for line in result.stdout.strip().split('\n'):
        if not line:
            continue
        parts = line.split(' ', 2)
        if len(parts) >= 2:
            commits.append({
                'hash': parts[0],
                'date': parts[1],
                'msg': parts[2] if len(parts) > 2 else ''
            })

    # Count LOC for each commit (excluding siui/)
    data = []
    for commit in commits:
        # Get all Python files in this commit
        result = subprocess.run(
            ['git', 'ls-tree', '-r', '--name-only', commit['hash']],
            capture_output=True, text=True, encoding='utf-8'
        )

        total_lines = 0
        for filepath in result.stdout.strip().split('\n'):
            if not filepath.endswith('.py'):
                continue
            # Exclude siui/ directory
            if 'siui/' in filepath or 'siui\\' in filepath:
                continue

            # Count lines in this file
            file_result = subprocess.run(
                ['git', 'show', f"{commit['hash']}:{filepath}"],
                capture_output=True, text=True, encoding='utf-8', errors='ignore'
            )
            if file_result.returncode == 0:
                total_lines += len(file_result.stdout.split('\n'))

        # Skip outliers (like accidentally committed venv)
        if total_lines > 50000:
            continue

        data.append({
            'date': commit['date'],
            'lines': total_lines,
            'msg': commit['msg'][:40]
        })
        print(f"{commit['date']}: {total_lines:>6} LOC - {commit['msg'][:50]}")

    return data


def generate_chart(data, output_path):
    """Generate the LOC chart."""
    if not data:
        print("No data to plot!")
        return

    # Filter to keep only significant changes (avoid cluttering)
    filtered = [data[0]]
    for d in data[1:]:
        if d['lines'] != filtered[-1]['lines']:
            filtered.append(d)

    dates = [datetime.strptime(d['date'], "%Y-%m-%d") for d in filtered]
    lines = [d['lines'] for d in filtered]

    # Create figure
    plt.style.use('default')
    fig, ax = plt.subplots(figsize=(10, 4))

    # Plot
    ax.fill_between(dates, lines, alpha=0.3, color='#4A90D9')
    ax.plot(dates, lines, 'o-', color='#2E6DB4', linewidth=2, markersize=5)

    # Formatting
    ax.set_xlabel('Date', fontsize=10)
    ax.set_ylabel('Lines of Code', fontsize=10)
    ax.set_title('Project Code Growth (Core Code)', fontsize=12, fontweight='bold')

    # Format x-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    plt.xticks(rotation=45)

    # Format y-axis
    ax.yaxis.set_major_formatter(plt.FuncFormatter(
        lambda x, p: f'{x/1000:.1f}K' if x >= 1000 else f'{x:.0f}'
    ))

    # Grid
    ax.grid(True, linestyle='--', alpha=0.7)
    ax.set_axisbelow(True)

    # Current stats annotation
    current_loc = lines[-1]
    ax.annotate(f'{current_loc:,} LOC', xy=(dates[-1], current_loc),
                xytext=(-60, 15), textcoords='offset points',
                fontsize=10, fontweight='bold',
                arrowprops=dict(arrowstyle='->', color='#2E6DB4'))

    plt.tight_layout()

    # Save
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
    print(f"\nChart saved to: {output_path}")

    return current_loc


def main():
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    output_path = project_root / 'docs' / 'loc_chart.png'

    print("Analyzing git history (excluding siui/)...\n")
    data = get_loc_history()

    print("\nGenerating chart...")
    loc = generate_chart(data, output_path)

    if loc:
        print(f"\nCurrent core code: {loc:,} lines")
        print("Run this script anytime to update the chart!")


if __name__ == '__main__':
    main()
