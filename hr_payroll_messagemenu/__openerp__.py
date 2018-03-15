# -*- coding: utf-8 -*-
##############################################################################
#
# OpenERP, Open Source Management Solution, third party addon
# Copyright (C) 2016- Vertel AB (<http://vertel.se>).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
{
'name': 'Payroll Message Menu',
'version': '0.1',
'summary': 'Human Resource',
'category': 'hr',
'description': """show time report menus in messaging menu

""",
'author': 'Vertel AB',
    'license': 'AGPL-3',
'website': 'http://www.vertel.se',
'depends': ['hr_timesheet_sheet', 'hr_payroll_flex100', 'hr_holidays','project'],
'data': ['hr_payroll_messagemenu_view.xml', 'hr_payroll_messagemenu_data.xml',],
'installable': True,
}
