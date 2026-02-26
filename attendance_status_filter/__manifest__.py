{
    "name": "Attendance Daily Report",
    "version": "1.0",
    "summary": "Daily Attendance Report with Absent Employees",
    "category": "Human Resources",
    "author": "Custom",
    "license": "LGPL-3",
    "depends": ["hr", "hr_attendance"],
    "data": [
        "security/ir.model.access.csv",
        "views/attendance_report_wizard_view.xml",
        "views/attendance_views.xml",
        "views/server_action.xml",
        "reports/attendance_report_action.xml",
        "reports/attendance_daily_report_template.xml",
    ],
    "installable": True,
}






# {
#     "name": "Attendance Daily Report",
#     "version": "1.0.0",
#     "summary": "Daily Attendance Report with Date Range and Absent Employees",
#     "description": """
#         Generate Daily Attendance Report with:
#         - Date Range Selection
#         - Today Button
#         - Present / Late / Miss Out / Absence
#         - All Employees Included
#         - PDF Report
#     """,
#     "author": "Custom",
#     "category": "Human Resources",
#     "license": "LGPL-3",
#     "depends": [
#         "hr",
#         "hr_attendance",
#     ],
#     "data": [
#         "security/ir.model.access.csv",
#         # Wizard View
#         "views/attendance_report_wizard_view.xml",
#         "views/attendance_views.xml",
#         # Report Action
#         "reports/attendance_report.xml",
#         # Report Template
#         "reports/attendance_report_template.xml",
#     ],
#     "installable": True,
#     "application": False,
#     "auto_install": False,
# }