# Defines every CRUD module shown on the admin dashboard.
# Add a new module here and a full Add / Edit / Delete / List page
# is generated automatically -- no new routes or templates needed.

MODULES = {
    "students": {
        "label": "Student Registration",
        "icon": "bi-person-badge",
        "fields": [
            {"name": "name", "label": "Full Name", "type": "text", "required": True},
            {"name": "roll_no", "label": "Roll No.", "type": "text", "required": True},
            {"name": "course", "label": "Course", "type": "text", "required": True},
            {"name": "room_no", "label": "Room No.", "type": "text", "required": False},
            {"name": "phone", "label": "Phone", "type": "text", "required": True},
            {"name": "email", "label": "Email", "type": "email", "required": False},
        ],
    },
    "rooms": {
        "label": "Smart Room Allocation",
        "icon": "bi-door-open",
        "fields": [
            {"name": "room_no", "label": "Room No.", "type": "text", "required": True},
            {"name": "block", "label": "Block", "type": "select",
             "choices": ["Boys", "Girls"], "required": True},
            {"name": "capacity", "label": "Capacity", "type": "number", "required": True},
            {"name": "occupied", "label": "Occupied", "type": "number", "required": True},
            {"name": "status", "label": "Status", "type": "select",
             "choices": ["Available", "Full", "Under Maintenance"], "required": True},
        ],
    },
    "visitors": {
        "label": "Visitor Management",
        "icon": "bi-person-lines-fill",
        "fields": [
            {"name": "visitor_name", "label": "Visitor Name", "type": "text", "required": True},
            {"name": "student_name", "label": "Meeting Student", "type": "text", "required": True},
            {"name": "room_no", "label": "Room No.", "type": "text", "required": False},
            {"name": "purpose", "label": "Purpose", "type": "text", "required": False},
            {"name": "entry_time", "label": "Entry Time", "type": "datetime-local", "required": True},
            {"name": "exit_time", "label": "Exit Time", "type": "datetime-local", "required": False},
        ],
    },
    "complaints": {
        "label": "Complaint Management",
        "icon": "bi-exclamation-triangle",
        "fields": [
            {"name": "student_name", "label": "Student Name", "type": "text", "required": True},
            {"name": "room_no", "label": "Room No.", "type": "text", "required": False},
            {"name": "subject", "label": "Subject", "type": "text", "required": True},
            {"name": "description", "label": "Description", "type": "textarea", "required": False},
            {"name": "status", "label": "Status", "type": "select",
             "choices": ["Pending", "In Progress", "Resolved"], "required": True},
        ],
    },
    "fees": {
        "label": "Fee Management",
        "icon": "bi-cash-coin",
        "fields": [
            {"name": "student_name", "label": "Student Name", "type": "text", "required": True},
            {"name": "room_no", "label": "Room No.", "type": "text", "required": False},
            {"name": "amount", "label": "Amount (Rs.)", "type": "number", "required": True},
            {"name": "due_date", "label": "Due Date", "type": "date", "required": False},
            {"name": "status", "label": "Status", "type": "select",
             "choices": ["Paid", "Unpaid", "Partial"], "required": True},
        ],
    },
    "notices": {
        "label": "Notice",
        "icon": "bi-megaphone",
        "fields": [
            {"name": "title", "label": "Title", "type": "text", "required": True},
            {"name": "content", "label": "Description", "type": "textarea", "required": True},
            {"name": "date", "label": "Date", "type": "date", "required": True},
            {"name": "faculty_name", "label": "Faculty Name", "type": "text", "required": True},
            {"name": "category", "label": "Category", "type": "select",
             "choices": ["General", "Academic", "Exam", "Event", "Hostel Rules", "Urgent"],
             "required": True},
            {"name": "pinned", "label": "Pin to Top", "type": "checkbox", "required": False},
        ],
    },
}
