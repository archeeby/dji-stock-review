"""DJI Stock Review v2 — compact review queue for laptop screens."""
import json
import subprocess
from pathlib import Path
import streamlit as st
from library_stats import get_library_stats
from review_navigation import candidate_order, next_after_decision
from trim_bounds import MIN_CLIP_SECONDS, editor_duration, normalize_trim, valid_trim
from candidate_reviews import key_for, get_review, review_status, status_label, save_review, undo_review

ROOT = Path.home() / "DroneStock"
WORK = ROOT / "metadata" / "videos"

st.set_page_config(page_title="DJI Stock Review v2", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>
/* Laptop-first: retain readable controls while removing Streamlit's default gaps. */
.block-container {max-width:100% !important;padding:3.6rem 0.85rem 1.2rem !important}
[data-testid="stVerticalBlock"] {gap:.26rem}
/* Preserve Streamlit column alignment rather than forcing every row to stretch. */
/* Bottom-align navigation and trim buttons with adjacent input widgets. */
div.st-key-review_navigation [data-testid="stHorizontalBlock"],
div.st-key-trim_controls [data-testid="stHorizontalBlock"] {align-items:flex-end !important}
div.st-key-review_navigation .stButton,
div.st-key-trim_controls .stButton {margin-bottom:0}
[data-testid="stWidgetLabel"] p {font-size:.75rem}
.stButton button {min-height:2.05rem;padding:.22rem .6rem}
.stTextArea textarea {min-height:54px}
[data-testid="stVideo"] {max-width:640px !important;margin:0 !important}
[data-testid="stVideo"] video {width:100% !important;max-height:305px !important;aspect-ratio:16/9;object-fit:contain;background:#000}
[data-testid="stCaptionContainer"] p {font-size:.72rem}
/* Reserve preview height during FFmpeg reruns to prevent action-button jumps. */
div.st-key-video_panel {min-height:490px !important}
div.st-key-preview_area {min-height:350px !important}
/* Only compact stats buttons, not the other action buttons. */
div[class*="st-key-stat_"] button {display:flex;flex-direction:row;align-items:center;
 justify-content:flex-start;gap:.3rem;min-height:2.45rem !important;padding:.3rem .6rem;
 border:1px solid rgba(130,130,130,.22);background:rgba(125,125,125,.055);width:100%}
div[class*="st-key-stat_"] button p {font-size:.86rem !important;line-height:1.35 !important;white-space:nowrap !important;text-align:left !important;margin:0 !important;overflow:visible !important}
/* Stable action row: do not overlay trim controls or the footer. */
div.st-key-review_actions {position:relative;z-index:1;
 background:var(--background-color,white);padding:.45rem .35rem;
 margin-top:.65rem;margin-bottom:.45rem;
 border-top:1px solid rgba(128,128,128,.24);
 border-bottom:1px solid rgba(128,128,128,.14)}
/* Avoid clipping text inside the small stat cards. */
div[class*="st-key-stat_"] {overflow:visible !important}
div[class*="st-key-stat_"] button {overflow:visible !important;min-height:2.7rem !important}

</style>""", unsafe_allow_html=True)

@st.cache_data(max_entries=4, show_spinner="Preparing preview...")
def preview_clip(source, mtime_ns, start, end):
    if end <= start:
        raise ValueError("End must be greater than Start")
    return subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(start),
        "-i", source, "-t", str(end-start), "-an", "-vf", "scale=960:-2",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-movflags", "+frag_keyframe+empty_moov", "-f", "mp4", "pipe:1",
    ], capture_output=True, check=True).stdout

def read_json(path, default):
    return json.loads(path.read_text()) if path.is_file() else default

def remove_export(folder_name, key):
    output = ROOT / "exports" / "approved" / folder_name
    for path in (output / key, output / (key + ".source.json")):
        if path.is_file():
            path.unlink()

def finish_undo(action):
    target = next((item for item in queue if item[0] == action["folder"]
                   and key_for(item[2], item[1]) == action["key"]), None)
    st.session_state["undo_target"] = target
    st.session_state["restore_undo_fields"] = target
    st.rerun()


def undo_last_decision():
    action = st.session_state["decision_history"].pop()
    restored = undo_review(WORK / action["folder"] / "reviews.json",
                           dict(action, previous_status="pending"),
                           preserve_edits=True)
    if review_status(restored) != "approved":
        remove_export(action["folder"], action["key"])
    finish_undo(action)

totals, videos = get_library_stats()
assert totals["candidates"] == totals["approved"] + totals["rejected"] + totals["pending"], "Review counts do not match"
head, export_summary = st.columns([3.4, 2], gap="small", vertical_alignment="center")
with head:
    st.markdown("**🎬 DJI Stock Review**  ·  Compact v2.3")
with export_summary:
    st.caption(f"Exported: {totals['exported']}  ·  Awaiting: {totals['needs_export'] + totals['outdated']}")

# Stats are always sourced from the same deduplicated library as the review queue.
stat_cols = st.columns([1, 1.2, 1, 1, 1], gap="small")
for col, name, count, filter_name in zip(
    stat_cols,
    ("Videos", "Candidates", "Approved", "Rejected", "Pending"),
    (totals["videos"], totals["candidates"], totals["approved"],
     totals["rejected"], totals["pending"]),
    (None, "All", "Approved", "Rejected", "Pending"),
):
    with col:
        if st.button(f"{name}: {count:,}", key=f"stat_{name.lower()}",
                     use_container_width=True, help=f"Filter by {filter_name}" if filter_name else "Total unique source videos"):
            if filter_name:
                st.session_state["queue_filter"] = filter_name
                st.session_state["queue_index"] = -1
                st.rerun()

# The stats module already deduplicates source videos; reuse its selected folders.
def queue_index(video_signature):
    result = []
    for folder_name in video_signature:
        folder = WORK / folder_name
        data = read_json(folder / "clip_candidates.json", {})
        for clip in sorted(data.get("clips", []), key=candidate_order):
            result.append((folder_name, clip["id"], data.get("source", "")))
    return result

queue = queue_index(tuple(v["folder"] for v in videos))
if not queue:
    st.warning("No clip candidates found")
    st.stop()

def review_statuses(signature):
    result = []
    for folder_name, clip_id, source in queue:
        reviews = read_json(WORK / folder_name / "reviews.json", {})
        review = get_review(reviews, source, clip_id)
        result.append(review_status(review))
    return result

# Read fresh statuses on every rerun, including external edits.
signature = tuple((v["folder"], (WORK / v["folder"] / "reviews.json").stat().st_mtime_ns
                   if (WORK / v["folder"] / "reviews.json").exists() else 0) for v in videos)
statuses = review_statuses(signature)

navigation_target = st.session_state.pop("navigation_target", None)
if navigation_target in queue:
    st.session_state.queue_index = queue.index(navigation_target)
undo_target = st.session_state.pop("undo_target", None)
if undo_target in queue:
    st.session_state.queue_index = queue.index(undo_target)
if "queue_index" not in st.session_state:
    st.session_state.queue_index = next((i for i, s in enumerate(statuses) if s == "pending"), 0)
if "queue_filter" not in st.session_state:
    st.session_state.queue_filter = "Pending"

navigation = st.container(key="review_navigation")
with navigation:
    filter_col, jump_col, prev_col, next_col = st.columns([1.2, 3.6, .6, .6], gap="small", vertical_alignment="bottom")
with filter_col:
    st.selectbox("Status", ["Pending", "All", "Approved", "Rejected"], key="queue_filter")
visible = [i for i, status in enumerate(statuses)
           if st.session_state.queue_filter == "All" or status == st.session_state.queue_filter.lower()]
if not visible:
    with jump_col:
        st.session_state["queue_selection"] = None
        st.selectbox("Clip", [], key="queue_selection", disabled=True,
                     placeholder="No matching clips")
    with prev_col:
        st.button("◀", use_container_width=True, disabled=True)
    with next_col:
        st.button("▶", use_container_width=True, disabled=True)
    st.info(f"No clips match the {st.session_state.queue_filter} status filter.")
    with st.container(key="review_actions"):
        _, _, empty_undo_col, _ = st.columns([1.2, 1.2, 1, 1.35], gap="small")
        with empty_undo_col:
            if st.button("↶ Undo", use_container_width=True,
                         disabled=not st.session_state.get("decision_history")):
                undo_last_decision()
    st.stop()
if st.session_state.queue_index not in visible:
    # Continue forward from the removed candidate, wrapping when necessary.
    st.session_state.queue_index = next(
        (i for i in visible if i > st.session_state.queue_index), visible[0])
with jump_col:
    # Synchronize the widget with navigation before rendering it.
    st.session_state["queue_selection"] = st.session_state.queue_index
    current_index = st.selectbox("Clip", visible,
        format_func=lambda i: f"{i+1}/{len(queue)} · {queue[i][2]} · {queue[i][1]} · {status_label(statuses[i])}",
        key="queue_selection",
        on_change=lambda: st.session_state.update(queue_index=st.session_state.queue_selection))
    st.session_state.queue_index = current_index
position = visible.index(current_index)
with prev_col:
    if st.button("◀", use_container_width=True, disabled=position == 0):
        st.session_state.queue_index = visible[position-1]
        st.rerun()
with next_col:
    if st.button("▶", use_container_width=True, disabled=position == len(visible)-1):
        st.session_state.queue_index = visible[position+1]
        st.rerun()

folder_name, clip_id, source_name = queue[current_index]
folder = WORK / folder_name
candidates_data = read_json(folder / "clip_candidates.json", {})
clip = next(c for c in candidates_data["clips"] if c["id"] == clip_id)
reviews_path = folder / "reviews.json"
reviews = read_json(reviews_path, {})
review_key = key_for(source_name, clip_id)
saved = get_review(reviews, source_name, clip_id)
record = read_json(folder / "stock_metadata" / f"{clip_id}.json", {})
metadata = record.get("metadata", {})
source_matches = list((ROOT / "originals").rglob(source_name)) if source_name else []
if len(source_matches) != 1:
    st.error(f"Expected exactly one original for {source_name}; found {len(source_matches)}")
    st.stop()
original = source_matches[0]
duration = float(candidates_data.get("duration") or 0)
if duration < MIN_CLIP_SECONDS:
    st.error("Source video must be at least 5 seconds long")
    st.stop()

st.caption(f"{source_name} · {clip_id} · {statuses[current_index].upper()} · {position+1}/{len(visible)} in filter")

# Stable widget keys per clip preserve unsaved text while comparing videos.
identity = f"{folder_name}:{clip_id}"
start_key, end_key = f"trim_start:{identity}", f"trim_end:{identity}"
if st.session_state.get("restore_undo_fields") == (folder_name, clip_id, source_name):
    st.session_state.pop("restore_undo_fields")
    # Restore before creating widgets; the action may have auto-navigated away.
    restored_keywords = saved.get("keywords", metadata.get("keywords", []))
    st.session_state.update({
        start_key: float(saved.get("start", clip["start"])),
        end_key: float(saved.get("end", clip["end"])),
        f"title:{identity}": saved.get("title", metadata.get("title", "")),
        f"description:{identity}": saved.get("description", metadata.get("description", "")),
        f"keywords:{identity}": ", ".join(restored_keywords) if isinstance(restored_keywords, list) else restored_keywords,
        f"note:{identity}": saved.get("note", ""),
    })
for k, value in ((start_key, float(saved.get("start", clip["start"]))),
                 (end_key, float(saved.get("end", clip["end"])))):
    if k not in st.session_state:
        st.session_state[k] = value

# Use an inward-rounded editor maximum without changing the source duration.
trim_max = editor_duration(duration)

def normalize_editor(changed=None):
    a, b = normalize_trim(st.session_state[start_key], st.session_state[end_key],
                          duration, changed)
    st.session_state[start_key] = a
    st.session_state[end_key] = b


def adjust_end(delta):
    """Adjust only End, keeping Start fixed and enforcing valid bounds."""
    from trim_bounds import adjust_trim_end
    st.session_state[end_key] = adjust_trim_end(
        st.session_state[start_key], st.session_state[end_key], duration, delta)


def reset_trim():
    a, b = normalize_trim(clip["start"], clip["end"], duration)
    st.session_state.update({start_key: a, end_key: b})


# Normalize candidates, saved reviews, Undo values and existing session values
# before either number_input is instantiated. This only updates the editor.
normalize_editor()

left, right = st.columns([1, 1], gap="small", vertical_alignment="top")
with left:
    with st.container(key="video_panel"):
        compare = st.toggle("Compare with original", key="compare_original", value=False)
        if compare:
            pcol, ocol = st.columns(2, gap="small")
        else:
            pcol, ocol = st.container(), None
        # Streamlit reruns immediately when Start/End changes. Render from live inputs.
        preview_start = float(st.session_state[start_key])
        preview_end = float(st.session_state[end_key])
        preview_valid = valid_trim(preview_start, preview_end, duration)
        with pcol:
            with st.container(key="preview_area"):
                st.caption("Selected clip")
                if preview_valid:
                    try:
                        st.video(preview_clip(str(original), original.stat().st_mtime_ns,
                                              preview_start, preview_end), format="video/mp4",
                                 autoplay=True)
                    except (subprocess.CalledProcessError, ValueError) as exc:
                        st.error(f"Preview failed: {exc}")
                else:
                    st.warning("Adjust Start/End to a valid range to preview.")
        if ocol is not None:
            with ocol:
                st.caption("Full original")
                st.video(str(original), start_time=int(preview_start))
        st.caption(f"Preview: {preview_start:.2f}–{preview_end:.2f}s · {preview_end-preview_start:.2f}s · {record.get('location', 'Unknown location')}")
        trim_controls = st.container(key="trim_controls")
        with trim_controls:
            start_col, end_col, minus_col, plus_col, reset_col = st.columns(
                [1, 1, .38, .38, .65], gap="small", vertical_alignment="bottom")
        with start_col:
            st.number_input("Start (s)", min_value=0.0, max_value=trim_max, step=0.1,
                            format="%.2f", key=start_key,
                            on_change=normalize_editor, args=("start",))
        with end_col:
            st.number_input("End (s)", min_value=0.0, max_value=trim_max, step=0.1,
                            format="%.2f", key=end_key,
                            on_change=normalize_editor, args=("end",))
        start, end = float(st.session_state[start_key]), float(st.session_state[end_key])
        valid = valid_trim(start, end, duration)
        with minus_col:
            st.button("−", key=f"trim_minus:{identity}", use_container_width=True,
                      disabled=end <= start + MIN_CLIP_SECONDS + 1e-9,
                      help="Shorten by 1 second", on_click=adjust_end, args=(-1.0,))
        with plus_col:
            st.button("+", key=f"trim_plus:{identity}", use_container_width=True,
                      disabled=end >= trim_max - 1e-9,
                      help="Extend by 1 second", on_click=adjust_end, args=(1.0,))
        with reset_col:
            st.button("Reset", help="Restore original AI-generated clip boundaries", use_container_width=True,
                      on_click=reset_trim)
        if not valid:
            st.error("Invalid trim: minimum 5 seconds; boundaries must be within source duration")
with right:
    tab_meta, tab_notes = st.tabs(["Stock metadata", "Notes"])
    with tab_meta:
        title = st.text_input("Title", value=saved.get("title", metadata.get("title", "")), key=f"title:{identity}")
        description = st.text_area("Description", value=saved.get("description", metadata.get("description", "")),
                                   height=85, key=f"description:{identity}")
        raw_keywords = saved.get("keywords", metadata.get("keywords", []))
        keywords = st.text_area("Keywords", value=", ".join(raw_keywords) if isinstance(raw_keywords, list) else raw_keywords,
                                height=85, key=f"keywords:{identity}")
    with tab_notes:
        note = st.text_area("Review notes", value=saved.get("note", ""), height=115, key=f"note:{identity}")

def collect(status):
    return {"status": status, "start": start, "end": end, "title": title.strip(),
            "description": description.strip(), "keywords": keywords.strip(), "note": note.strip()}

def save_decision(status):
    if not valid:
        st.error("Invalid boundaries")
        return
    action = save_review(reviews_path, source_name, clip_id, collect(status))
    action.update(folder=folder_name, index=current_index)
    st.session_state.setdefault("decision_history", []).append(action)
    if status == "rejected":
        remove_export(folder_name, review_key)
    updated_statuses = list(statuses)
    updated_statuses[current_index] = status
    next_i = next_after_decision(queue, updated_statuses, current_index,
                                 st.session_state.queue_filter)
    if next_i is not None:
        # Resolve identity after rerunning, rather than relying on an old index.
        st.session_state["navigation_target"] = queue[next_i]
    st.rerun()

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
actions = st.container(key="review_actions")
with actions:
    reject_col, approve_col, undo_col, export_col = st.columns([1.2, 1.2, 1, 1.35], gap="small")
    with reject_col:
        if st.button("❌ Reject", use_container_width=True, disabled=not valid):
            save_decision("rejected")
    with approve_col:
        if st.button("✅ Approve", type="primary", use_container_width=True, disabled=not valid):
            save_decision("approved")
    with undo_col:
        selected_decided = review_status(saved) in ("approved", "rejected")
        if st.button("↶ Undo", use_container_width=True,
                     disabled=not selected_decided and not st.session_state.get("decision_history"),
                     help="Return selected reviewed clip to Pending" if selected_decided
                     else "Undo the last decision after automatic navigation"):
            if selected_decided:
                # Persisted decisions are reversible even in a fresh session.
                # The selected candidate takes precedence over unrelated history.
                save_review(reviews_path, source_name, clip_id, collect("pending"))
                action = {"folder": folder_name, "key": review_key}
                st.session_state["decision_history"] = [
                    item for item in st.session_state.get("decision_history", [])
                    if (item["folder"], item["key"]) != (folder_name, review_key)]
                remove_export(folder_name, review_key)
            else:
                undo_last_decision()
            # Undo does not recreate exports removed by Reject.
            finish_undo(action)
    with export_col:
        if st.button("📦 Export approved", use_container_width=True):
            st.session_state["show_export"] = not st.session_state.get("show_export", False)

st.caption("Originals are never modified. Reject removes existing exported copies; Undo restores the decision, not deleted MP4s.")

if st.session_state.get("show_export", False):
    st.markdown("##### Final export")
    import fcntl
    import sys

    LOCK_FILE = ROOT / "metadata" / "export.lock"

    if "export_feedback" in st.session_state:
        feedback = st.session_state.pop("export_feedback")
        if feedback["failures"]:
            st.error(f'Export finished with {len(feedback["failures"])} error(s).')
        else:
            st.success(f'Export completed: {feedback["completed"]} video(s). Statuses refreshed.')
        with st.expander("Export details"):
            st.code(chr(10).join(feedback["details"] + feedback["failures"]))

    st.caption("Only approved clips are exported. Original videos are never modified.")

    def run_exports(export_folders):
        LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)

        with LOCK_FILE.open("a+") as lock:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                st.warning("An export is already running in another session.")
                return

            total = 0
            for export_folder in export_folders:
                candidates_file = export_folder / "clip_candidates.json"
                data = json.loads(candidates_file.read_text())
                total += len(data.get("clips", []))

            progress = st.progress(0, text="Starting export...")
            status_text = st.empty()
            completed = 0
            successes = 0
            details = []
            failures = []

            try:
                for index, export_folder in enumerate(export_folders, 1):
                    status_text.info(
                        f"Video {index}/{len(export_folders)}: {export_folder.name}"
                    )

                    process = subprocess.Popen(
                        [
                            sys.executable,
                            "-u",
                            str(ROOT / "export_approved.py"),
                            export_folder.name,
                        ],
                        cwd=str(ROOT),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                    )

                    output_lines = []

                    for line in process.stdout:
                        line = line.rstrip()
                        output_lines.append(line)

                        if line.startswith("PROGRESS|"):
                            parts = line.split("|", 3)
                            if len(parts) == 4:
                                completed += 1
                                progress.progress(
                                    min(completed / max(total, 1), 1.0),
                                    text=f"{completed}/{total} clips processed",
                                )
                                status_text.info(
                                    f"Video {index}/{len(export_folders)} · "
                                    f"Clip {parts[3]}"
                                )

                    returncode = process.wait()

                    if returncode == 0:
                        successes += 1
                        details.append(f"{export_folder.name}: OK")
                    else:
                        failures.append(
                            f"{export_folder.name}: " + "\\n".join(output_lines[-15:])
                        )
                        # Count unfinished clips so the progress represents
                        # all attempted work, including failed videos.
                        expected = len(json.loads(
                            (export_folder / "clip_candidates.json").read_text()
                        ).get("clips", []))
                        reported = sum(
                            line.startswith("PROGRESS|") for line in output_lines
                        )
                        completed += max(expected - reported, 0)
                        progress.progress(
                            min(completed / max(total, 1), 1.0),
                            text=f"{completed}/{total} clips attempted",
                        )

                progress.progress(1.0, text="Export batch finished.")
                st.session_state["export_feedback"] = {
                    "completed": successes,
                    "details": details,
                    "failures": failures,
                }

                # Play one notification after the entire export batch finishes.
                try:
                    subprocess.Popen(
                        ["afplay", "/System/Library/Sounds/Glass.aiff"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except OSError:
                    pass
            finally:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

        st.rerun()


    if "export_in_progress" not in st.session_state:
        st.session_state["export_in_progress"] = False


    def start_all_export():
        st.session_state["export_in_progress"] = True
        st.session_state["export_requested"] = "all"

    st.warning("Export writes MP4 files to exports/approved. Review your selections first.")
    st.button(
        "Start export of approved clips" if not st.session_state["export_in_progress"] else "Exporting...",
        use_container_width=False,
        disabled=st.session_state["export_in_progress"],
        on_click=start_all_export,
        key="export_all_button",
    )

    request = st.session_state.pop("export_requested", None)

    if request:
        if request == "all":
            export_folders = [WORK / video["folder"] for video in videos]
        else:
            export_folders = [folder]

        try:
            run_exports(export_folders)
        finally:
            st.session_state["export_in_progress"] = False
