import threading
from models.models import Department, Bench, RoomAllocation, SHIFTS


class ExamScheduler:
    def __init__(self, room_benches):
        self.room_benches = room_benches
        self.total_rooms = len(room_benches)
        self.total_seats_per_shift = sum(room_benches) * 2
        self.lock = threading.Lock()
        self.room_slots = {}
        self.all_dept_names = []
        self._init_day(1)

    def _init_day(self, day):
        for shift in SHIFTS:
            for r_idx, num_b in enumerate(self.room_benches, start=1):
                key = (day, shift, r_idx)
                if key not in self.room_slots:
                    self.room_slots[key] = RoomAllocation(
                        room_id=r_idx, day=day, shift=shift, num_benches=num_b
                    )

    def _get_max_day(self):
        max_d = 0
        for key in self.room_slots.keys():
            if key[0] > max_d:
                max_d = key[0]
        return max_d

    def _add_new_day(self):
        new_day = self._get_max_day() + 1
        self._init_day(new_day)
        return new_day

    def _get_rooms_for(self, day, shift):
        rooms = []
        for r in range(1, self.total_rooms + 1):
            key = (day, shift, r)
            if key in self.room_slots:
                rooms.append(self.room_slots[key])
        return rooms

    def _total_remaining_benches(self, day, shift):
       
        total = 0
        rooms = self._get_rooms_for(day, shift)
        for room in rooms:
            for bench in room.benches:
                if not bench.pos_a_dept and not bench.pos_b_dept:
                    total += 1
        return total

    def _book_dept_pair(self, dept_a_name, dept_a_students, dept_b_name, dept_b_students, day, shift):
        avail_benches = self._total_remaining_benches(day, shift)
        if avail_benches == 0:
            return {}, 0, 0, dept_a_students, dept_b_students

        benches_needed = max(dept_a_students, dept_b_students)
        benches_to_use = min(benches_needed, avail_benches)

        placed_a = min(dept_a_students, benches_to_use)
        placed_b = min(dept_b_students, benches_to_use)

        rooms = self._get_rooms_for(day, shift)
        benches_filled = 0

        rooms_summary_a = {}
        rooms_summary_b = {}

        for room in rooms:
            if benches_filled >= benches_to_use:
                break

            for bench in room.benches:
                if benches_filled >= benches_to_use:
                    break

                if not bench.pos_a_dept and not bench.pos_b_dept:
                    if benches_filled < placed_a:
                        bench.pos_a_dept = dept_a_name
                        rooms_summary_a[room.room_id] = rooms_summary_a.get(room.room_id, 0) + 1

                    if benches_filled < placed_b:
                        bench.pos_b_dept = dept_b_name
                        rooms_summary_b[room.room_id] = rooms_summary_b.get(room.room_id, 0) + 1

                    benches_filled += 1

        overflow_a = dept_a_students - placed_a
        overflow_b = dept_b_students - placed_b

        return rooms_summary_a, rooms_summary_b, placed_a, placed_b, overflow_a, overflow_b

    def run(self, departments):
        self.all_dept_names = [d.name for d in departments]
        
        sorted_depts = sorted(departments, key=lambda d: d.num_students, reverse=True)
        
        all_assignments = []
        all_warnings = []

        dept_queue = list(sorted_depts)

        while dept_queue:
            if len(dept_queue) >= 2:
                dept_a = dept_queue.pop(0)
                dept_b = dept_queue.pop(0)

                max_exams = max(dept_a.num_exams, dept_b.num_exams)

                days_used_a = set()
                days_used_b = set()

                for ex_i in range(1, max_exams + 1):
                    has_a = ex_i <= dept_a.num_exams
                    has_b = ex_i <= dept_b.num_exams

                    req_a = dept_a.num_students if has_a else 0
                    req_b = dept_b.num_students if has_b else 0

                    scheduled = False
                    with self.lock:
                        slots_set = set()
                        for key in self.room_slots.keys():
                            slots_set.add((key[0], key[1]))
                        all_slots = sorted(list(slots_set), key=lambda x: (x[0], SHIFTS.index(x[1])))

                        for day, shift in all_slots:
                            if (has_a and day in days_used_a) or (has_b and day in days_used_b):
                                continue
                            if self._total_remaining_benches(day, shift) == 0:
                                continue

                            res_a, res_b, pl_a, pl_b, ov_a, ov_b = self._book_dept_pair(
                                dept_a.name, req_a, dept_b.name, req_b, day, shift
                            )

                            if has_a:
                                days_used_a.add(day)
                                summary_a = [{"room_id": rid, "students": cnt} for rid, cnt in sorted(res_a.items())]
                                all_assignments.append({
                                    "dept": dept_a.name, "exam_num": ex_i, "day": day, "shift": shift,
                                    "rooms": summary_a, "placed": pl_a, "total": dept_a.num_students
                                })
                                if ov_a > 0:
                                    all_warnings.append(f"{dept_a.name} Exam {ex_i} (Day {day}, {shift}): {pl_a}/{dept_a.num_students} placed — ⚠️ {ov_a} overflow!")

                            if has_b:
                                days_used_b.add(day)
                                summary_b = [{"room_id": rid, "students": cnt} for rid, cnt in sorted(res_b.items())]
                                all_assignments.append({
                                    "dept": dept_b.name, "exam_num": ex_i, "day": day, "shift": shift,
                                    "rooms": summary_b, "placed": pl_b, "total": dept_b.num_students
                                })
                                if ov_b > 0:
                                    all_warnings.append(f"{dept_b.name} Exam {ex_i} (Day {day}, {shift}): {pl_b}/{dept_b.num_students} placed — ⚠️ {ov_b} overflow!")

                            scheduled = True
                            break

                        if not scheduled:
                            new_day = self._add_new_day()
                            res_a, res_b, pl_a, pl_b, ov_a, ov_b = self._book_dept_pair(
                                dept_a.name, req_a, dept_b.name, req_b, new_day, "Morning"
                            )

                            if has_a:
                                days_used_a.add(new_day)
                                summary_a = [{"room_id": rid, "students": cnt} for rid, cnt in sorted(res_a.items())]
                                all_assignments.append({
                                    "dept": dept_a.name, "exam_num": ex_i, "day": new_day, "shift": "Morning",
                                    "rooms": summary_a, "placed": pl_a, "total": dept_a.num_students
                                })
                                if ov_a > 0:
                                    all_warnings.append(f"{dept_a.name} Exam {ex_i} (Day {new_day}, Morning): {pl_a}/{dept_a.num_students} placed — ⚠️ {ov_a} overflow!")

                            if has_b:
                                days_used_b.add(new_day)
                                summary_b = [{"room_id": rid, "students": cnt} for rid, cnt in sorted(res_b.items())]
                                all_assignments.append({
                                    "dept": dept_b.name, "exam_num": ex_i, "day": new_day, "shift": "Morning",
                                    "rooms": summary_b, "placed": pl_b, "total": dept_b.num_students
                                })
                                if ov_b > 0:
                                    all_warnings.append(f"{dept_b.name} Exam {ex_i} (Day {new_day}, Morning): {pl_b}/{dept_b.num_students} placed — ⚠️ {ov_b} overflow!")

            else:
                single_dept = dept_queue.pop(0)
                all_warnings.append(f"⚠️ {single_dept.name} is the only department scheduled in this slot. To prevent cheating, 1 student per bench is allocated (Right seat left empty).")

                days_used_s = set()
                for ex_i in range(1, single_dept.num_exams + 1):
                    scheduled = False
                    with self.lock:
                        slots_set = set()
                        for key in self.room_slots.keys():
                            slots_set.add((key[0], key[1]))
                        all_slots = sorted(list(slots_set), key=lambda x: (x[0], SHIFTS.index(x[1])))

                        for day, shift in all_slots:
                            if day in days_used_s:
                                continue
                            if self._total_remaining_benches(day, shift) == 0:
                                continue

                            res_a, _, pl_a, _, ov_a, _ = self._book_dept_pair(
                                single_dept.name, single_dept.num_students, "", 0, day, shift
                            )

                            days_used_s.add(day)
                            summary_a = [{"room_id": rid, "students": cnt} for rid, cnt in sorted(res_a.items())]
                            all_assignments.append({
                                "dept": single_dept.name, "exam_num": ex_i, "day": day, "shift": shift,
                                "rooms": summary_a, "placed": pl_a, "total": single_dept.num_students
                            })
                            if ov_a > 0:
                                all_warnings.append(f"{single_dept.name} Exam {ex_i} (Day {day}, {shift}): {pl_a}/{single_dept.num_students} placed — ⚠️ {ov_a} overflow!")
                            scheduled = True
                            break

                        if not scheduled:
                            new_day = self._add_new_day()
                            res_a, _, pl_a, _, ov_a, _ = self._book_dept_pair(
                                single_dept.name, single_dept.num_students, "", 0, new_day, "Morning"
                            )
                            days_used_s.add(new_day)
                            summary_a = [{"room_id": rid, "students": cnt} for rid, cnt in sorted(res_a.items())]
                            all_assignments.append({
                                "dept": single_dept.name, "exam_num": ex_i, "day": new_day, "shift": "Morning",
                                "rooms": summary_a, "placed": pl_a, "total": single_dept.num_students
                            })
                            if ov_a > 0:
                                all_warnings.append(f"{single_dept.name} Exam {ex_i} (Day {new_day}, Morning): {pl_a}/{single_dept.num_students} placed — ⚠️ {ov_a} overflow!")

        
        self.finalize_labels()

        all_assignments.sort(key=lambda a: (a["day"], SHIFTS.index(a["shift"]), a["dept"]))

        return {
            "schedule": all_assignments,
            "room_plan": self._build_room_plan(),
            "warnings": all_warnings,
            "total_days": self._get_max_day(),
            "total_seats_per_shift": self.total_seats_per_shift
        }

    def finalize_labels(self):
        slots_set = set()
        for key in self.room_slots.keys():
            slots_set.add((key[0], key[1]))
        
        slot_keys = sorted(list(slots_set), key=lambda x: (x[0], SHIFTS.index(x[1])))

        for day, shift in slot_keys:
            rooms = self._get_rooms_for(day, shift)
            rooms.sort(key=lambda r: r.room_id)

            dept_counters = {}

            for room in rooms:
                for bench in room.benches:
                    if bench.pos_a_dept:
                        dept = bench.pos_a_dept
                        dept_counters[dept] = dept_counters.get(dept, 0) + 1
                        bench.pos_a_label = f"{dept}-{dept_counters[dept]}"

                    if bench.pos_b_dept:
                        dept = bench.pos_b_dept
                        dept_counters[dept] = dept_counters.get(dept, 0) + 1
                        bench.pos_b_label = f"{dept}-{dept_counters[dept]}"

    def _build_room_plan(self):
        plan = []
        days_set = set()
        for key in self.room_slots.keys():
            days_set.add(key[0])

        for day in sorted(list(days_set)):
            for shift in SHIFTS:
                rooms = []
                for r in self._get_rooms_for(day, shift):
                    if r.get_occupied() > 0:
                        rooms.append(r)

                if not rooms:
                    continue

                rooms_data = []
                for r in sorted(rooms, key=lambda x: x.room_id):
                    bench_grid = []
                    for b in r.benches:
                        bench_grid.append({
                            "bench": b.bench_number,
                            "pos_a_dept": b.pos_a_dept,
                            "pos_a_label": b.pos_a_label,
                            "pos_b_dept": b.pos_b_dept,
                            "pos_b_label": b.pos_b_label
                        })

                    rooms_data.append({
                        "room_id": r.room_id,
                        "num_benches": r.num_benches,
                        "capacity": r.capacity,
                        "occupied": r.get_occupied(),
                        "remaining": r.get_remaining(),
                        "depts": r.get_dept_names(),
                        "bench_grid": bench_grid
                    })

                plan.append({
                    "day": day,
                    "shift": shift,
                    "rooms": rooms_data
                })

        return plan