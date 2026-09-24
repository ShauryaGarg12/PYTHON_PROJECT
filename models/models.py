SHIFTS = ["Morning", "Afternoon", "Evening"]

class Department:
    def __init__(self, name, num_students, num_exams):
        self.name = name
        self.num_students = int(num_students)
        self.num_exams = int(num_exams)


class Bench:
    def __init__(self, bench_number):
        self.bench_number = bench_number
        self.pos_a_dept = ""
        self.pos_a_label = ""
        self.pos_b_dept = ""
        self.pos_b_label = ""


class RoomAllocation:
    def __init__(self, room_id, day, shift, num_benches):
        self.room_id = room_id
        self.day = day
        self.shift = shift
        self.num_benches = num_benches
        self.capacity = num_benches * 2
        self.benches = [Bench(b) for b in range(1, num_benches + 1)]

    def get_occupied(self):
        count = 0
        for b in self.benches:
            if b.pos_a_dept:
                count += 1
            if b.pos_b_dept:
                count += 1
        return count

    def get_remaining(self):
        return self.capacity - self.get_occupied()

    def get_dept_names(self):
        dept_list = []
        for b in self.benches:
            if b.pos_a_dept and b.pos_a_dept not in dept_list:
                dept_list.append(b.pos_a_dept)
            if b.pos_b_dept and b.pos_b_dept not in dept_list:
                dept_list.append(b.pos_b_dept)
        return dept_list 