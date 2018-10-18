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

from odoo import tools
from odoo import models, fields, api, _

import odoo.tools
from datetime import datetime, timedelta
from odoo import SUPERUSER_ID

import logging
_logger = logging.getLogger(__name__)



class hr_attendance(models.Model):
    _inherit = 'hr.attendance'

    @api.one
    def _flextime(self):

        def get_attendance_intervals(att):
            res = []
            pair = []
            for a in att:
                if a.action == 'sign_in' and not pair:
                    pair.append(fields.Datetime.from_string(a.name))
                elif a.action == 'sign_out' and len(pair) == 1:
                    pair.append(fields.Datetime.from_string(a.name))
                    res.append(pair)
                    pair = []
            return res

        if self.employee_id.sudo().contract_id and self._check_last_sign_out(self) and self.employee_id.sudo().contract_id.working_hours:
            today = fields.Datetime.from_string(self.name).replace(hour=0, minute=0, microsecond=0)
            tomorrow = fields.Datetime.to_string(today + timedelta(days=1))
            if self.employee_id.user_id:
                resource = self.env['resource.resource'].search([('resource_type', '=', 'user'), ('user_id', '=', self.employee_id.user_id.id)])
            else:
                resource = None
            flextime = 0.0
            leaves = self.employee_id.sudo().contract_id.working_hours.get_leave_intervals(resource_id = resource and resource.id or None)[0]
            for holiday in self.env['hr.holidays'].search([('date_from', '>=', fields.Datetime.to_string(today)),('date_to', '<', tomorrow), ('employee_id', '=', self.employee_id.id), ('type', '=', 'remove')]):
                leaves.append((fields.Datetime.from_string(holiday.date_from), fields.Datetime.from_string(holiday.date_to)))
            job_intervals = self.env['resource.calendar'].get_working_intervals_of_day(start_dt=today, leaves=leaves)
            for i in range(len(job_intervals)):
                job_intervals[i] = list(job_intervals[i])
            attendances = self.env['hr.attendance'].sudo().search([('employee_id','=',self.employee_id.id),('name','>',self.name[:10] + ' 00:00:00'),('name','<',self.name[:10] + ' 23:59:59')],order='name')
            _logger.debug('job_intervals: %s' % job_intervals)
            _logger.debug('att: %s' % attendances)
            attendance_intervals = get_attendance_intervals(attendances)
            _logger.debug('attendance_intervals: %s' % attendance_intervals)
            # Easier than keeping track of when we add new intervals to job_intervals
            missing_intervals = []
            if job_intervals and attendance_intervals:
                # Positive flex time can only occur before first or after last interval
                if job_intervals[0][0] > attendance_intervals[0][0]:
                    flextime += (job_intervals[0][0] - attendance_intervals[0][0]).total_seconds()
                    _logger.debug('1: %s' % flextime)
                if job_intervals[-1][1] < attendance_intervals[-1][1]:
                    flextime += (attendance_intervals[-1][1] - job_intervals[-1][1]).total_seconds()
                    _logger.debug('2: %s' % flextime)
                for a_i in attendance_intervals:
                    _logger.debug('attendance_interval: %s' % a_i)
                    i = 0
                    while i < len(job_intervals):
                        j_i = job_intervals[i]
                        # a_i intersects j_i if it starts before job interval ends, and ends after j_i starts
                        if a_i[0] <= j_i[1] and a_i[1] >= j_i[0]:
                            if a_i[0] <= j_i[0] and a_i[1] >= j_i[1]:
                                # j_i is completely inside a_i
                                del job_intervals[i]
                                _logger.debug('\n1 deleted\n')
                            else:
                                if a_i[0] > j_i[0]:
                                    # a_i starts after j_i
                                    missing_intervals.append([j_i[0], a_i[0]])
                                if a_i[1] < j_i[1]:
                                    # a_i ends before j_i. Replace start time of j_i
                                    j_i[0] = a_i[1]
                                    _logger.debug('\n2 changed\n')
                                    i += 1
                                else:
                                    del job_intervals[i]
                                    _logger.debug('\n2 deleted\n')
                            _logger.debug('\n%s: %s' % (i, job_intervals))
                        else:
                            i += 1
                _logger.debug('job_intervals: %s' % (job_intervals + missing_intervals))
                # Any remaining intervals have not been worked
                for j_i in job_intervals + missing_intervals:
                    flextime -= (j_i[1] - j_i[0]).seconds
                    _logger.debug('\nflextime: %s\n' % flextime)
            self.flextime = round(flextime / 60.0)
    flextime = fields.Integer(compute='_flextime', string='Flex Time (m)')

    @api.one
    def _flex_working_hours(self):
        flex_working_hours = 0.0
        leaves = 0.0
        if self._check_last_sign_out(self):
            att = self.env['hr.attendance'].sudo().search([('employee_id','=',self.employee_id.id),('ckeck_in','>',self.ckeck_in[:10] + ' 00:00:00'),('check_out','<',self.check_out[:10] + ' 23:59:59')],order='check_in')
            _logger.warn(att)
            job_intervals = self.env['resource.calendar'].get_working_intervals_of_day(start_dt=fields.Datetime.from_string(self.ckeck_in).replace(hour=0,minute=0))
            _logger.warn(job_intervals)
            if len(job_intervals) > 0:
                if self.flextime > 0.0: #if got positive flex time, worked flex = worked on schedule + flex time
                    self.flex_working_hours = self.get_working_hours + self.flextime / 60.0
                elif self.flextime < 0.0: #if got negative flex time, worked flex = planned hours + flex time
                    self.flex_working_hours = self.working_hours_on_day + self.flextime / 60.0
                elif self.flextime == 0.0: #if got 0 flex time
                    if fields.Datetime.from_string(att[0].name) < job_intervals[0][0] or fields.Datetime.from_string(att[-1].name) > job_intervals[-1][-1]: #if extra worked time is out of schedule, so fill up missed hours in schedule
                        self.flex_working_hours = self.working_hours_on_day
                    elif fields.Datetime.from_string(att[0].name) >= job_intervals[0][0] or fields.Datetime.from_string(att[-1].name) <= job_intervals[-1][-1]: #if not, take worked hours in schedule
                        self.flex_working_hours = self.get_working_hours

    flex_working_hours = fields.Float(compute='_flex_working_hours', string='Worked Flex (h)')

    @api.one
    def _flextime_month(self):
        year = datetime.now().year
        month = datetime.now().month
        date_start = datetime(year, month, 1)
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1
        date_end = datetime(year, month, 1) - timedelta(days=1)
        self.flextime_month = round(sum(self.search([('employee_id', '=',self.employee_id.id), ('check_in', '>', fields.Date.to_string(date_start) + ' 00:00:00'), ('check_out', '<', fields.Date.to_string(date_end) + ' 23:59:59')]).mapped("flextime")))
    flextime_month = fields.Integer(compute="_flextime_month")

    @api.one
    def _compensary_leave(self):
        self.compensary_leave = self.with_context({'employee_id': self.employee_id.id}).env.ref("hr_holidays.holiday_status_comp").remaining_leaves * 60 * (self.employee_id.get_working_hours_per_day() or 8)
    compensary_leave = fields.Float(compute='_compensary_leave')

    flextime_total = fields.Float('Flextime Bank', compute='_get_flextime_total')

    @api.one
    def _get_flextime_total(self):
        self.flextime_total = self.employee_id.get_unbanked_flextime() + self.compensary_leave

class hr_payslip(models.Model):
    _inherit = 'hr.payslip'

    @api.one
    def _flextime(self):
        self.flextime = sum(self.env['hr.attendance'].search([('employee_id', '=',self.employee_id.id), ('check_in', '>', self.date_from + ' 00:00:00'), ('check_out', '<', self.date_to + ' 23:59:59')]).mapped("flextime"))
        self.flex_working_hours = sum(self.env['hr.attendance'].search([('employee_id','=',self.employee_id.id),('check_in','>',self.date_from + ' 00:00:00'),('check_out','<',self.date_to + ' 23:59:59')]).mapped("flex_working_hours"))
    flextime = fields.Float(string='Flex Time This Period (m)',compute="_flextime")
    flex_working_hours = fields.Float(compute='_flextime', string='Worked Flex (h)')

    @api.one
    def _flex_working_days(self):
        self.flex_working_days = len(self.env['hr.attendance'].search([('employee_id', '=',self.employee_id.id), ('check_in', '>', self.date_from + ' 00:00:00'), ('check_out', '<', self.date_to + ' 23:59:59')]).filtered(lambda a: a._check_last_sign_out(a) == True))
    flex_working_days = fields.Float(compute='_flex_working_days', string='Flex Worked Days')
    @api.one

    def _compensary_leave(self):
        # TODO: Fix issues with leaves spanning two or more months.
        if self.state == 'draft':
            holidays = self.env['hr.holidays'].search([('employee_id', '=', self.employee_id.id), ('holiday_status_id', '=', self.env.ref("hr_holidays.holiday_status_comp").id), ('date_to', '<', self.date_to + ' 23:59:59')])
            self.write({'compensary_leave': sum(holidays.filtered(lambda h: h.type == 'add').mapped("number_of_days_temp")) - sum(holidays.filtered(lambda h: h.type == 'remove').mapped("number_of_days_temp"))})
        self.total_compensary_leave = self.compensary_leave + (self.flextime / 60.0 / 24.0)
    compensary_leave = fields.Float(string='Compensary Leave', compute="_compensary_leave", store=True)
    total_compensary_leave = fields.Float(string='Total Compensary Leave',compute="_compensary_leave")



    #~ @api.model
    #~ def get_worked_day_lines(self,contract_ids, date_from, date_to, context=None):

        #~ return super(hr_payslip,self).get_worked_day_lines(contract_ids,date_from,date_to)



    @api.one
    def Xcompute_sheet(self):
        super(hr_payslip,self).compute_sheet()
        work100 = self.worked_days_line_ids.filtered(lambda l: l.code == 'WORK100' or l.code == 'FLEX100')
        number_of_hours = work100.number_of_hours
        number_of_days  = work100.number_of_days
        work100.write({'code': 'WORK100'})
        work100.write({'number_of_hours': self.flex_working_hours})
        _logger.warn('hours %s days %s flex %s days %s' % (number_of_hours,number_of_days,self.flex_working_hours,self._get_nbr_of_days()))
        return True

    def Xget_worked_day_lines(self, contract_ids, date_from, date_to):
        """
        @param contract_ids: list of contract id
        @return: returns a list of dict containing the input that should be applied for the given contract between date_from and date_to
        """
        def was_on_leave(employee_id, datetime_day):
            res = False
            day = datetime_day.strftime("%Y-%m-%d")
            holiday_ids = self.env['hr.holidays'].search([('state','=','validate'),('employee_id','=',employee_id),('type','=','remove'),('date_from','<=',day),('date_to','>=',day)])
            if holiday_ids:
                res = self.env['hr.holidays'].browse(holiday_ids).holiday_status_id.name
            return res

        res = []
        contract = self.env['hr.contract'].browse(contract_ids)
        if not contract.working_hours:
            #fill only if the contract as a working schedule linked
            return False
        attendances = {
             'name': _("Normal Working Days paid at 100%"),
             'sequence': 1,
             'code': 'WORK100',
             'number_of_days': 0.0,
             'number_of_hours': 0.0,
             'contract_id': contract.id,
        }
        leaves = {}
        day_from = datetime.strptime(date_from,"%Y-%m-%d")
        day_to = datetime.strptime(date_to,"%Y-%m-%d")
        nb_of_days = (day_to - day_from).days + 1
        for day in range(0, nb_of_days):
            working_hours_on_day = self.env['resource.calendar'].working_hours_on_day(day_from + timedelta(days=day))
            if working_hours_on_day:
                #the employee had to work
                leave_type = was_on_leave(contract.employee_id.id, day_from + timedelta(days=day), context=context)
                if leave_type:
                    #if he was on leave, fill the leaves dict
                    if leave_type in leaves:
                        leaves[leave_type]['number_of_days'] += 1.0
                        leaves[leave_type]['number_of_hours'] += working_hours_on_day
                    else:
                        leaves[leave_type] = {
                            'name': leave_type,
                            'sequence': 5,
                            'code': leave_type,
                            'number_of_days': 1.0,
                            'number_of_hours': working_hours_on_day,
                            'contract_id': contract.id,
                        }
                else:
                    #add the input vals to tmp (increment if existing)
                    attendances['number_of_days'] += 1.0
                    attendances['number_of_hours'] += working_hours_on_day
        leaves = [value for key,value in leaves.items()]
        res += [attendances] + leaves
        return res

    @api.one
    def hr_verify_sheet(self):
        #TODO: Make sure this is only written once.
        if self.state == 'draft':
            self.employee_id.set_flex_time_pot(self.flextime, self.date_to)
        return super(hr_payslip, self).hr_verify_sheet()


class hr_employee(models.Model):
    _inherit = 'hr.employee'

    #flex_holiday_id = fields.Many2one(comodel_name='hr.holidays', string='Flex Time Bank')

    def set_flex_time_pot(self, minutes, date = fields.Datetime.now()):
        values = {
            'name': _('Flex Time for %s (%s)') % (self.name, date),
            'holiday_status_id': self.env.ref("hr_holidays.holiday_status_comp").id,
            'employee_id': self.id,
            'type': 'add' if minutes >= 0.0 else 'remove' ,
            'state': 'validate',
            'number_of_minutes': abs(minutes),
            'date_flextime': date,
            'date_from': '1900-01-01 00:00:00',
        }
        last = self.env['hr.holidays'].search([('employee_id', '=', self.id), ('date_flextime', '!=', False), ('date_to', '!=', False)], limit = 1, order = 'date_flextime desc')
        if last:
            values['date_from'] = fields.Datetime.to_string(fields.Datetime.from_string(last.date_to) + timedelta(seconds = 1))
        values['date_to'] = fields.Datetime.to_string(fields.Datetime.from_string(values['date_from']) + timedelta(minutes = abs(minutes)))
        holiday = self.env['hr.holidays'].search([('employee_id', '=', self.id), ('date_flextime', '=', date)])
        if holiday:
            holiday.write(values)
        else:
            holiday = self.env['hr.holidays'].create(values)
        holiday.holidays_validate()

    @api.multi
    def get_unbanked_flextime(self):
        """Returns all flextime since last payslip."""
        self.ensure_one()
        slip = self.env['hr.payslip'].sudo().search([('date_to', '<=', fields.Date.today()), ('state', '=', 'done')], limit = 1, order = 'date_to desc')
        if slip:
            attendances = self.env['hr.attendance'].search_read([('employee_id', '=', self.id), ('action', '=', 'sign_out'), ('name', '>', slip.date_to)], ['flextime'])
        else:
            attendances = self.env['hr.attendance'].search_read([('employee_id', '=', self.id)], ['flextime'])
        res = 0
        for attendance in attendances:
            res += attendance['flextime']
        return res

    @api.one
    def check_flextime_limit(self):
        """Checks if flextime has passed the warning limit."""
        _logger.warn(self.name)
        _logger.warn(self.get_flextime_total())
        # Flextidsgräns per schema
        if self.contract_id and self.contract_id.working_hours and self.contract_id.working_hours.flextime_warning and abs(self.get_flextime_total()) > self.contract_id.working_hours.flextime_warning:
            subject = 'Flextime overdue %s' % self.name
            _logger.warn(subject)
            if not self.env['mail.nodup'].check_dup(self.user_id.partner_id.email, subject):
                partner_ids = []
                if self.user_id:
                    partner_ids.append(self.user_id.partner_id.id)
                if self.parent_id and self.parent_id.user_id:
                    partner_ids.append(self.parent_id.user_id.partner_id.id)
                if partner_ids:
                    id = self.env['mail.message'].create({
                            'body': _("Flextime overdue %s minutes for %s\n" % (self.get_flextime_total(), self.name)),
                            'subject': subject,
                            'author_id': self.env.user.partner_id.id,
                            'partner_ids': [(6, 0, partner_ids)],
                            'res_id': self.id,
                            'model': self._name,
                            'type': 'email',
                        })
            _logger.info('Flextime overdue:  %s hours for %s ' % (self.get_flextime_total(), self.name))

    @api.multi
    def get_flextime_total(self):
        self.ensure_one()
        return self.get_unbanked_flextime() + self.with_context({'employee_id': self.id}).env.ref("hr_holidays.holiday_status_comp").remaining_leaves * 60 * (self.get_working_hours_per_day() or 8)

    @api.model
    def run_flextime_limit_check(self):
        _logger.info("Running flextime limit check")
        for employee in self.search([]):
            employee.check_flextime_limit()

class hr_timesheet_sheet(models.Model):
    _inherit = "hr_timesheet_sheet.sheet"

    @api.one
    @api.depends('attendances_ids','attendances_ids.sheet_id')
    def _flex_working_hours(self):
        self.flex_working_hours = sum(self.attendances_ids.mapped('flex_working_hours'))
        self.flextime = sum(self.attendances_ids.mapped('flextime'))
    flex_working_hours = fields.Float(compute='_flex_working_hours', string='Worked Flex (h)')
    flextime = fields.Float(compute='_flex_working_hours', string='Flex Time This Period(m)')

    @api.one
    def _compensary_leave(self):
        self.compensary_leave = self.with_context({'employee_id': self.employee_id.id}).env.ref("hr_holidays.holiday_status_comp").remaining_leaves * 60 * (self.employee_id.get_working_hours_per_day() or 8)
    compensary_leave = fields.Float(string='Compensary Leave (d)', compute='_compensary_leave')
    flextime_total = fields.Float('Flextime Bank', compute='_get_flextime_total')

    @api.one
    def _get_flextime_total(self):
        self.flextime_total = self.employee_id.get_unbanked_flextime() + self.compensary_leave

class hr_holidays(models.Model):
    _inherit='hr.holidays'

    date_flextime = fields.Date('Flextime Date', help = "This leave is a flextime total up until this date (presumably covering the entire month).")

    @api.one
    def _ps_max_leaves(self):
        slip = self.env['hr.payslip'].browse(self._context.get('slip_id',None))
        if slip:
            holiday_ids = self.env['hr.holidays'].search([('holiday_status_id','=',self.id),('state','=','validate'),('employee_id','=',slip.employee_id.id),('date_from','>=',slip.date_from),('date_to','<=',slip.date_to)])
            self.ps_max_leaves = sum(holiday_ids.filtered(lambda h: h.type == 'add').mapped('number_of_days_temp'))
            self.ps_leaves_taken = sum(holiday_ids.filtered(lambda h: h.type == 'remove').mapped('number_of_days_temp'))
    ps_max_leaves = fields.Integer(string='Max Leaves',compute='_ps_max_leaves')
    ps_leaves_taken = fields.Integer(string='Max Leaves',compute='_ps_max_leaves')

class hr_holidays_status(models.Model):
    _inherit = "hr.holidays.status"

    @api.multi
    def name_get(self):
        """Add flex time to name."""
        res = super(hr_holidays_status, self).name_get()
        if self._context.get('employee_id', False):
            employee = self.env['hr.employee'].browse(self._context.get('employee_id'))
            for hs in self:
                if hs == self.env.ref("hr_holidays.holiday_status_comp"):
                    for i in range(0, len(res)):
                        if res[i][0] == hs.id:
                            res[i] = (hs.id, res[i][1] + ('  (%g m/%g m)' % ((hs.leaves_taken or 0.0) * 60 * (employee.get_working_hours_per_day() or 8), (hs.max_leaves or 0.0) * 60 * (employee.get_working_hours_per_day() or 8))))
        return res

class hr_contract_type(models.Model):
    _inherit = 'hr.contract.type'

    work_time = fields.Selection(selection_add=[('flex','Flex Time')])

class ResourceCalendar(models.Model):
    _inherit = 'resource.calendar'

    flextime_warning = fields.Integer(string='Flextime Warning Limit', help="Send warning mails to employee and boss when this limit is passed.", default=480)

class hr_holidays_earning(models.Model):
    _name = "hr.holidays.earning"
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
