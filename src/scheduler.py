"""scheduler.py - Scheduler Agent. Books the earliest FREE slot; can never double-book."""
import sqlite3


def book_interview(conn, application_id):
    # already has a slot? return the same one (safe to call twice)
    row = conn.execute("SELECT slot_id, start_time, panelist FROM slots WHERE application_id=?",
                       (application_id,)).fetchone()
    if row:
        return {"ok": True, "slot_id": row[0], "start_time": row[1], "panelist": row[2]}

    free = conn.execute("SELECT slot_id, start_time, panelist FROM slots WHERE status='FREE' "
                        "ORDER BY start_time").fetchall()
    for slot_id, start_time, panelist in free:
        try:
            with conn:
                cur = conn.execute("UPDATE slots SET status='BOOKED', application_id=? "
                                   "WHERE slot_id=? AND status='FREE'", (application_id, slot_id))
        except sqlite3.IntegrityError:           # this application got a slot meanwhile
            return book_interview(conn, application_id)
        if cur.rowcount == 1:                    # we really got it
            return {"ok": True, "slot_id": slot_id, "start_time": start_time, "panelist": panelist}
        # rowcount 0 -> someone else booked it first, try the next slot
    return {"ok": False, "reason": "no interview slot available"}
