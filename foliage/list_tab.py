'''
list_tab.py: implementation of the "List UUIDs" tab
'''

from   commonpy.data_utils import unique, pluralized, flattened
from   commonpy.file_utils import exists, readable
from   commonpy.interrupt import wait
from   pprint import pformat
import pyperclip
from   pywebio.input import input, select, checkbox, radio
from   pywebio.input import NUMBER, TEXT, input_update, input_group
from   pywebio.output import put_text, put_markdown, put_row, put_html
from   pywebio.output import toast, popup, close_popup, put_buttons, put_button, put_error
from   pywebio.output import use_scope, set_scope, clear, remove, put_warning
from   pywebio.output import put_success, put_info, put_table, put_grid, span
from   pywebio.output import put_tabs, put_image, put_scrollable, put_code, put_link
from   pywebio.output import put_processbar, set_processbar, put_loading
from   pywebio.output import put_column
from   pywebio.pin import pin, pin_wait_change, put_input, put_actions
from   pywebio.pin import put_textarea, put_radio, put_checkbox, put_select
from   sidetrack import set_debug, log
import threading

from   .export_utils import export
from   .folio import Folio, RecordKind, RecordIdKind, TypeKind, NAME_KEYS
from   .ui import alert, warn, confirm, notify


# Tab creation function.
# .............................................................................

def list_tab():
    return [
        put_grid([[
            put_markdown('Select a FOLIO type to list:').style('margin-top: 6px'),
            put_select('list_type', options = [
                {'label': 'Acquisition units', 'value': TypeKind.ACQUISITION_UNIT},
                {'label': 'Address types', 'value': TypeKind.ADDRESS},
                {'label': 'Alternative title types', 'value': TypeKind.ALT_TITLE},
                {'label': 'Call number types', 'value': TypeKind.CALL_NUMBER},
                {'label': 'Classification types', 'value': TypeKind.CLASSIFICATION},
                {'label': 'Contributor types', 'value': TypeKind.CONTRIBUTOR},
                {'label': 'Contributor name types', 'value': TypeKind.CONTRIBUTOR_NAME},
                {'label': 'Department types', 'value': TypeKind.DEPARTMENT},
                {'label': 'Expense classes', 'value': TypeKind.EXPENSE_CLASS},
                {'label': 'Fixed due date schedules', 'value': TypeKind.FIXED_DUE_DATE_SCHED},
                {'label': 'Group types', 'value': TypeKind.GROUP},
                {'label': 'Holdings types', 'value': TypeKind.HOLDINGS},
                {'label': 'Holdings note types', 'value': TypeKind.HOLDINGS_NOTE},
                {'label': 'Holdings source types', 'value': TypeKind.HOLDINGS_SOURCE},
                {'label': 'Identifier types', 'value': TypeKind.ID},
                {'label': 'ILL policy types', 'value': TypeKind.ILL_POLICY},
                {'label': 'Instance types', 'value': TypeKind.INSTANCE},
                {'label': 'Instance format types', 'value': TypeKind.INSTANCE_FORMAT},
                {'label': 'Instance note types', 'value': TypeKind.INSTANCE_NOTE},
                {'label': 'Instance relationship types', 'value': TypeKind.INSTANCE_REL},
                {'label': 'Instance status types', 'value': TypeKind.INSTANCE_STATUS},
                {'label': 'Item note types', 'value': TypeKind.ITEM_NOTE},
                {'label': 'Item damaged status types', 'value': TypeKind.ITEM_DAMAGED_STATUS},
                {'label': 'Loan types', 'value': TypeKind.LOAN},
                {'label': 'Loan policy types', 'value': TypeKind.LOAN_POLICY},
                {'label': 'Location types', 'value': TypeKind.LOCATION},
                {'label': 'Material types', 'value': TypeKind.MATERIAL},
                {'label': 'Nature of content term types', 'value': TypeKind.NATURE_OF_CONTENT},
#                {'label': 'Order lines', 'value': TypeKind.ORDER_LINE},
                {'label': 'Organizations', 'value': TypeKind.ORGANIZATION},
                {'label': 'Service point types', 'value': TypeKind.SERVICE_POINT},
                {'label': 'Shelf location types', 'value': TypeKind.SHELF_LOCATION},
                {'label': 'Statistical code types', 'value': TypeKind.STATISTICAL_CODE},
            ]).style('margin-left: 10px; margin-bottom: 0'),
            put_button('Get list', onclick = lambda: do_list(),
                       ).style('margin-left: 10px; text-align: left'),
            put_button(' Clear ', outline = True, onclick = lambda: clear_tab()
                       ).style('margin-left: 10px; text-align: right'),
        ]])
    ]


# Miscellaneous helper functions.
# .............................................................................

def clear_tab():
    clear('output')


def do_list():
    log(f'listing id types')
    folio = Folio()
    with use_scope('output', clear = True):
        put_processbar('bar', init = 1/2)
        requested = pin.list_type
        try:
            types = folio.types(requested)
        except Exception as ex:
            log(f'exception requesting list of {requested}: ' + str(ex))
            put_html('<br>')
            put_error('Error: ' + str(ex))
            return
        finally:
            set_processbar('bar', 2/2)
        cleaned_name = requested.split('/')[-1].replace("-", " ")
        put_row([
            put_markdown(f'Found {len(types)} values for {cleaned_name}:'
                         ).style('margin-left: 17px; margin-top: 6px'),
            put_button('Export', outline = True,
                       onclick = lambda: export(types, requested),
                       ).style('text-align: right; margin-right: 17px'),
        ]).style('margin-top: 15px; margin-bottom: 14px')
        key = NAME_KEYS[requested] if requested in NAME_KEYS else 'name'
        rows = []
        type_list = [(item[key], item['id']) for item in types]
        for name, id in type_list:
            title = f'Data for {cleaned_name} value "{name.title()}"'
            action = lambda: show_record(title, id, requested)
            rows.append([name,
                         link(id, action).style('margin-top: 0.25em; margin-bottom: 0.5em'),
                         copy_button(id).style('padding: 0')])

        contents = [[put_markdown('**Name**'), put_markdown('**Id**'), put_text('')]]
        contents += sorted(rows, key = lambda x: x[0])
        put_grid(contents, cell_widths = 'auto auto 106px')


def show_record(title, id, record_type):
    folio = Folio()
    try:
        data  = folio.records(id, RecordIdKind.TYPE_ID, record_type)
    except Exception as ex:
        alert(str(ex))
        return

    event = threading.Event()

    def clk(val):
        event.set()

    data  = data[0] if isinstance(data, list) and len(data) > 0 else data
    pins  = [
        put_scrollable(put_code(pformat(data, indent = 2)), height = 400),
        put_buttons([{'label': 'Close', 'value': 1}], onclick = clk).style('float: right'),
    ]
    popup(title = title, content = pins, closable = False, size = 'large')

    event.wait()
    close_popup()


def link(name, action):
    return put_button(name, onclick = action, link_style = True).style('margin-left: 0')


def copy_button(text):
    return put_button('Copy id', onclick = lambda: pyperclip.copy(text), outline = True,
                      small = True, color = 'primary').style('text-align: center')
