import os

def save_schedule_to_file(schedule, room_plan, filename="saved_schedules/latest_schedule.txt"):
    # Ensure directory exists
    os.makedirs("saved_schedules", exist_ok=True)
    
    # 1. File Open (Write mode)
    f = open(filename, "w", encoding="utf-8")
    
    # Header
    f.write("=== EXAM SCHEDULE & SEATING PLAN ===\n\n")
    
    # 2. Write Exam Schedule
    f.write("--- EXAM TIMETABLE ---\n")
    for row in schedule:
        f.write(f"Day {row['day']} | Shift: {row['shift']} | Dept: {row['dept']} | Exam {row['exam_num']} | Students: {row['placed']}/{row['total']}\n")
    
    f.write("\n\n")
    
    # 3. Write Room Seating Plan
    f.write("--- SEATING PLAN ---\n")
    for slot in room_plan:
        f.write(f"\nDay {slot['day']} - Shift: {slot['shift']}\n")
        
        for room in slot['rooms']:
            f.write(f"\nRoom {room['room_id']} (Benches: {room['num_benches']})\n")
            # Fixed width column headers
            f.write(f"{'Bench':<12} {'Left Seat':<15} {'Right Seat':<15}\n")
            f.write("-" * 42 + "\n")
            
            for b in room['bench_grid']:
                left = b['pos_a_dept'] if b['pos_a_dept'] else "Empty"
                right = b['pos_b_dept'] if b['pos_b_dept'] else "Empty"
                bench_str = f"Bench {b['bench']}"
                # Alignment properly set using fixed width
                f.write(f"{bench_str:<12} {left:<15} {right:<15}\n")
                
    # 4. File Close
    f.close()
    return filename