{
    "name": "Biotime Integration",
    "version": "19.0.1.0",
    "summary": "Biotime Biodata, Terminals and Attendance Sync",
    "category": "HR",
    "depends": ["hr"],
    "data": [
         "security/ir.model.access.csv", 
       
        "views/biotime_terminal_view.xml",
        "views/biotime_biodata_view.xml",
        "views/hr_attendance_line_view.xml",
         "views/biotime_menu.xml",
        "views/bio_time_service_views.xml"

    ], 
    "installable": True,
    'application': True,
    'license': 'LGPL-3',
}









