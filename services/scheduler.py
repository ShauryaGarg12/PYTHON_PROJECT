import threading
from models.models import RoomAllocation, SHIFTS
from services.file_saver import save_schedule_to_file

class ExamScheduler:
    def __init__(self, room_benches):
        self.room_benches = room_benches
        self.total_rooms = len(room_benches)
        self.total_seats_per_shift = sum(room_benches) * 2
        self.lock = threading.Lock()
        self.room_slots = {}
        self._init_day(1)

    def _init_day(self, day):
        for shift in SHIFTS:
            for r_idx, num_b in enumerate(self.room_benches, start=1):
                key = (day, shift, r_idx)
                if key not in self.room_slots:
                    self.room_slots[key] = RoomAllocation(room_id=r_idx, day=day, shift=shift, num_benches=num_b)

    def _get_max_day(self):
        return max([key[0] for key in self.room_slots.keys()], default=0)

    def _add_new_day(self):
        new_day = self._get_max_day() + 1
        self._init_day(new_day)
        return new_day

    def _get_rooms_for(self, day, shift):
        return [self.room_slots[(day, shift, r)] for r in range(1, self.total_rooms + 1) if (day, shift, r) in self.room_slots]

    def _total_remaining_benches(self, day, shift):
        return sum(1 for room in self._get_rooms_for(day, shift) for b in room.benches if not b.pos_a_dept and not b.pos_b_dept)

    def _book_dept_pair(self, dept_a_name, dept_a_students, dept_b_name, dept_b_students, day, shift):
        avail_benches = self._total_remaining_benches(day, shift)
        if avail_benches == 0:
            return {}, 0, 0, dept_a_students, dept_b_students

        benches_needed = max(dept_a_students, dept_b_students)
        benches_to_use = min(benches_needed, avail_benches)

        placed_a = min(dept_a_students, benches_to_use)
        placed_b = min(dept_b_students, benches_to_use)

        rooms_summary_a, rooms_summary_b = {}, {}
        benches_filled = 0

        for room in self._get_rooms_for(day, shift):
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

        return rooms_summary_a, rooms_summary_b, placed_a, placed_b, dept_a_students - placed_a, dept_b_students - placed_b

    def _record_assignment(self, dept_name, ex_i, day, shift, summary, placed, total, warnings):
        summary_list = [{"room_id": rid, "students": cnt} for rid, cnt in sorted(summary.items())]
        overflow = total - placed
        if overflow > 0:
            warnings.append(f"{dept_name} Exam {ex_i} (Day {day}, {shift}): {placed}/{total} placed — ⚠️ {overflow} overflow!")
        
        return {
            "dept": dept_name, "exam_num": ex_i, "day": day, "shift": shift,
            "rooms": summary_list, "placed": placed, "total": total
        }

    def run(self, departments):
        sorted_depts = sorted(departments, key=lambda d: d.num_students, reverse=True)
        all_assignments, all_warnings, dept_queue = [], [], list(sorted_depts)

        while dept_queue:
            if len(dept_queue) >= 2:
                dept_a, dept_b = dept_queue.pop(0), dept_queue.pop(0)
                max_exams = max(dept_a.num_exams, dept_b.num_exams)
                days_a, days_b = set(), set()

                for ex_i in range(1, max_exams + 1):
                    has_a, has_b = ex_i <= dept_a.num_exams, ex_i <= dept_b.num_exams
                    req_a = dept_a.num_students if has_a else 0
                    req_b = dept_b.num_students if has_b else 0

                    with self.lock:
                        all_slots = sorted(list({(k[0], k[1]) for k in self.room_slots.keys()}), key=lambda x: (x[0], SHIFTS.index(x[1])))
                        target_day, target_shift = None, None

                        for day, shift in all_slots:
                            if (has_a and day in days_a) or (has_b and day in days_b):
                                continue
                            if self._total_remaining_benches(day, shift) > 0:
                                target_day, target_shift = day, shift
                                break

                        if not target_day:
                            target_day, target_shift = self._add_new_day(), "Morning"

                        res_a, res_b, pl_a, pl_b, _, _ = self._book_dept_pair(dept_a.name, req_a, dept_b.name, req_b, target_day, target_shift)

                        if has_a:
                            days_a.add(target_day)
                            all_assignments.append(self._record_assignment(dept_a.name, ex_i, target_day, target_shift, res_a, pl_a, dept_a.num_students, all_warnings))
                        if has_b:
                            days_b.add(target_day)
                            all_assignments.append(self._record_assignment(dept_b.name, ex_i, target_day, target_shift, res_b, pl_b, dept_b.num_students, all_warnings))

            else:
                s_dept = dept_queue.pop(0)
                all_warnings.append(f"⚠️ {s_dept.name} is single department in slot. 1 student per bench allocated.")
                days_s = set()

                for ex_i in range(1, s_dept.num_exams + 1):
                    with self.lock:
                        all_slots = sorted(list({(k[0], k[1]) for k in self.room_slots.keys()}), key=lambda x: (x[0], SHIFTS.index(x[1])))
                        target_day, target_shift = None, None

                        for day, shift in all_slots:
                            if day not in days_s and self._total_remaining_benches(day, shift) > 0:
                                target_day, target_shift = day, shift
                                break

                        if not target_day:
                            target_day, target_shift = self._add_new_day(), "Morning"

                        res_a, _, pl_a, _, _, _ = self._book_dept_pair(s_dept.name, s_dept.num_students, "", 0, target_day, target_shift)
                        days_s.add(target_day)
                        all_assignments.append(self._record_assignment(s_dept.name, ex_i, target_day, target_shift, res_a, pl_a, s_dept.num_students, all_warnings))

        self.finalize_labels()
        all_assignments.sort(key=lambda a: (a["day"], SHIFTS.index(a["shift"]), a["dept"]))
        room_plan = self._build_room_plan()
        saved_file_path = save_schedule_to_file(all_assignments, room_plan)

        return {
            "schedule": all_assignments,
            "room_plan": room_plan,
            "warnings": all_warnings,
            "total_days": self._get_max_day(),
            "total_seats_per_shift": self.total_seats_per_shift,
            "saved_file": saved_file_path
        }

    def finalize_labels(self):
        all_slots = sorted(list({(k[0], k[1]) for k in self.room_slots.keys()}), key=lambda x: (x[0], SHIFTS.index(x[1])))
        for day, shift in all_slots:
            rooms = sorted(self._get_rooms_for(day, shift), key=lambda r: r.room_id)
            dept_counters = {}
            for room in rooms:
                for b in room.benches:
                    if b.pos_a_dept:
                        dept_counters[b.pos_a_dept] = dept_counters.get(b.pos_a_dept, 0) + 1
                        b.pos_a_label = f"{b.pos_a_dept}-{dept_counters[b.pos_a_dept]}"
                    if b.pos_b_dept:
                        dept_counters[b.pos_b_dept] = dept_counters.get(b.pos_b_dept, 0) + 1
                        b.pos_b_label = f"{b.pos_b_dept}-{dept_counters[b.pos_b_dept]}"

    def _build_room_plan(self):
        plan = []
        days = sorted(list({k[0] for k in self.room_slots.keys()}))
        for day in days:
            for shift in SHIFTS:
                rooms = [r for r in self._get_rooms_for(day, shift) if r.get_occupied() > 0]
                if not rooms:
                    continue
                rooms_data = [{
                    "room_id": r.room_id, "num_benches": r.num_benches, "capacity": r.capacity,
                    "occupied": r.get_occupied(), "remaining": r.get_remaining(), "depts": r.get_dept_names(),
                    "bench_grid": [{
                        "bench": b.bench_number, "pos_a_dept": b.pos_a_dept, "pos_a_label": b.pos_a_label,
                        "pos_b_dept": b.pos_b_dept, "pos_b_label": b.pos_b_label
                    } for b in r.benches]
                } for r in sorted(rooms, key=lambda x: x.room_id)]

                plan.append({"day": day, "shift": shift, "rooms": rooms_data})
        return plan 
