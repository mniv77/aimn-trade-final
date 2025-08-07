# file: async_taskgroup_with_match.py
import asyncio
import random
import argparse
import sqlite3
import csv
import json
import traceback
import matplotlib.pyplot as plt
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
import time

@dataclass
class WorkerTask:
    name: str

    @staticmethod
    async def run(name: str, retries: int = 2):
        attempt = 0
        while attempt <= retries:
            try:
                await asyncio.sleep(random.uniform(0.1, 0.5))
                if random.choice([True, False]):
                    return f"{name} completed successfully on attempt {attempt + 1}."
                else:
                    raise RuntimeError(f"{name} failed on attempt {attempt + 1}.")
            except RuntimeError as e:
                if attempt == retries:
                    raise e
                attempt += 1

def init_db():
    conn = sqlite3.connect("task_results.db")
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS results (
            timestamp TEXT,
            task_name TEXT,
            status TEXT,
            message TEXT,
            duration REAL
        )
    """)
    conn.commit()
    return conn

def visualize_summary(status_counts, save_as_pdf: bool):
    labels = list(status_counts.keys())
    values = list(status_counts.values())

    plt.bar(labels, values)
    plt.xlabel("Status")
    plt.ylabel("Count")
    plt.title("Task Status Summary")
    plt.tight_layout()
    filename = "task_summary.pdf" if save_as_pdf else "task_summary.png"
    plt.savefig(filename)
    plt.show()

def visualize_histogram(durations):
    plt.hist(durations, bins=10, edgecolor='black')
    plt.xlabel("Duration (s)")
    plt.ylabel("Task Count")
    plt.title("Histogram of Task Durations")
    plt.tight_layout()
    plt.savefig("duration_histogram.png")
    plt.show()

def load_results_from_db(filter_status: str, top_n: int, top_status: str, export_json: bool):
    conn = sqlite3.connect("task_results.db")
    cur = conn.cursor()
    cur.execute("SELECT timestamp, task_name, status, message, duration FROM results")
    rows = cur.fetchall()
    conn.close()

    filtered = [(ts, task, status, msg, dur) for ts, task, status, msg, dur in rows
                if not filter_status or filter_status.upper() == status.upper()]

    status_counts = Counter(status for _, _, status, _, _ in filtered)
    duration_totals = defaultdict(list)
    durations = []
    for _, _, status, _, dur in filtered:
        duration_totals[status].append(dur)
        durations.append(dur)

    print("\nLoaded Summary:")
    summary = {}
    for status, count in status_counts.items():
        avg_dur = sum(duration_totals[status]) / len(duration_totals[status]) if duration_totals[status] else 0
        print(f"{status}: {count} (avg duration: {avg_dur:.3f}s)")
        summary[status] = {"count": count, "avg_duration": avg_dur}

    if top_n > 0:
        print(f"\nTop {top_n} longest-running tasks:")
        top_rows = sorted(filtered, key=lambda r: r[4], reverse=True)
        if top_status:
            top_rows = [r for r in top_rows if r[2].upper() == top_status.upper()]
        for ts, task, status, msg, dur in top_rows[:top_n]:
            print(f"{task} | {status} | {dur:.3f}s")

    if export_json:
        with open("summary_metrics.json", "w") as jf:
            json.dump(summary, jf, indent=2)
        print("Summary metrics exported to summary_metrics.json")

    visualize_histogram(durations)

    return [(status, msg) for _, _, status, msg, _ in filtered], status_counts

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run async tasks with retry and log to SQLite.")
    parser.add_argument("--retries", type=int, default=2, help="Number of retries per task")
    parser.add_argument("--export-csv", action="store_true", help="Export results to task_results.csv")
    parser.add_argument("--export-json", action="store_true", help="Export summary to summary_metrics.json")
    parser.add_argument("--visualize", action="store_true", help="Show bar chart of task result summary")
    parser.add_argument("--save-pdf", action="store_true", help="Save chart as PDF instead of PNG")
    parser.add_argument("--filter-status", type=str, default="", help="Only show summary for this status (e.g. ERROR)")
    parser.add_argument("--from-db", action="store_true", help="Load and display results from SQLite DB")
    parser.add_argument("--top", type=int, default=0, help="Display top N longest-running tasks")
    parser.add_argument("--top-status", type=str, default="", help="Filter top N results by status (e.g. SUCCESS)")
    args = parser.parse_args()

    asyncio.run(load_results_from_db(
        args.filter_status,
        args.top,
        args.top_status,
        args.export_json
    ))
