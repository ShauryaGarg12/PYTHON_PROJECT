from flask import Blueprint, request, jsonify
from models.models import Department
from services.scheduler import ExamScheduler

api_bp = Blueprint('api', __name__)

@api_bp.route('/schedule', methods=['POST'])
def schedule():
    data = request.get_json()

    try:
        room_benches = [int(b) for b in data['room_benches']]
        departments_raw = data['departments']
    except (KeyError, ValueError):
        return jsonify({'error': 'Invalid input data.'}), 400

    if not room_benches or any(b <= 0 for b in room_benches):
        return jsonify({'error': 'Number of benches must be positive numbers.'}), 400

    if not departments_raw:
        return jsonify({'error': 'Add at least one department.'}), 400

    departments = []
    for d in departments_raw:
        name = d.get('name', '').strip().upper()
        if not name:
            return jsonify({'error': 'Department name cannot be empty.'}), 400
        departments.append(Department(
            name=name,
            num_students=int(d['students']),
            num_exams=int(d['exams'])
        ))

    scheduler = ExamScheduler(room_benches)
    result = scheduler.run(departments)
    return jsonify(result)
