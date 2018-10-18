# -*- coding: utf-8 -*-
##############################################################################
#
#    Odoo, Open Source Enterprise Management Solution, third party addon
#    Copyright (C) 2018 Vertel AB (<http://vertel.se>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from odoo import models, fields, api, _, tools
import odoo.tools
from datetime import datetime, timedelta
import time
import re

from openerp.exceptions import except_orm, Warning, RedirectWarning

import logging
_logger = logging.getLogger(__name__)

class hr_timesheet_sheet(models.Model):
    _inherit = "hr_timesheet_sheet.sheet"

    @api.multi
    def name_get(self):
        if not len(self)>0:
            return []
        return [(t.id, _('Week ')+fields.Date.from_string(t.date_from).strftime('%y%U')) for t in self]


class messagemenu_change_project(models.TransientModel):
    _name = 'messagemenu.change_project'

    @api.multi
    def change_project(self):
        assert len(self) == 1,  'This option should only be used for a single id at a time.' # Ensure only one
        employee = self.env['hr.employee'].search([('user_id','=',self._uid)])
        if not employee:
            raise Warnin(_("You lack employment, please contact your HR-officer"))
        attendances = self.env['hr.attendance'].search([('employee_id', '=', employee.id), ('action', '!=', 'action')], limit=2, order='name desc')
        last_attendance = sec_last_attendance = None
        if len(attendances) == 2:
            last_attendance = attendances[0]
            sec_last_attendance = attendances[1]
            if last_attendance.action == sec_last_attendance.action:
                raise Warning(_('You cannot %s twice' %last_attendance.action))
        elif len(attendances) == 1:
            last_attendance = attendances[0]
        if last_attendance:
            if last_attendance.action == 'sign_in' and self.project_id:
                last_attendance.project_id = self.project_id.id
            elif last_attendance.action == 'sign_out' and sec_last_attendance.action == 'sign_in' and sec_last_attendance.project_id:
                timesheet = self.env['hr.analytic.timesheet'].create({
                    'date': last_attendance.name[:10],
                    'account_id': sec_last_attendance.project_id.analytic_account_id.id,
                    'name': '/',
                    'unit_amount': (fields.Datetime.from_string(last_attendance.name) - fields.Datetime.from_string(sec_last_attendance.name)).total_seconds() / 3600.0,
                    'user_id': employee.user_id.id,
                    'product_id': request.env['hr.analytic.timesheet'].with_context(user_id = employee.user_id.id, employee_id = employee.id)._getEmployeeProduct(),
                    'product_uom_id': request.env['hr.analytic.timesheet'].with_context(user_id = employee.user_id.id, employee_id = employee.id)._getEmployeeUnit(),
                    'general_account_id': request.env['hr.analytic.timesheet'].with_context(user_id = employee.user_id.id, employee_id = employee.id)._getGeneralAccount(),
                    'journal_id': request.env['hr.analytic.timesheet'].with_context(user_id = employee.user_id.id, employee_id = employee.id)._getAnalyticJournal(),
                })
        else:
            raise Warning(_('There is no active attendance'))
        return True
    ### Fields
    project_id = fields.Many2one(comodel_name='project.project',string="Project",help="My projects",)

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
