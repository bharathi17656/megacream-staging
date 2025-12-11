/** @odoo-module **/

import { AttendanceGanttRowProgressBar as BaseProgressBar } from "@hr_attendance_gantt/attendance_gantt/attendance_row_progress_bar";

import { patch } from "@web/core/utils/patch";

import { registry } from "@web/core/registry";

patch(BaseProgressBar.prototype, {
     setup() {
        super.setup(...arguments);
        console.log("this is our planning method 1",this.props)
     },
     
    normalHours() {
       console.log("this is our planning method")
         return 2
    }

});


