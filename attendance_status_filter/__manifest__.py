{
    "name": "Attendance Status & Today Filter",
    "version": "1.0",
    "depends": ["hr_attendance"],
    "author": "Custom",
    "category": "HR",
    "summary": "Adds Status field, Today filter and Daily PDF Report in Attendance",
    "data": [
        # Views
        "views/attendance_views.xml",
        # Reports
        "reports/attendance_report.xml",
        "reports/attendance_report_template.xml",
    ],
    "installable": True,
    "application": False,
}