'''
lookup_tab.py: implementation of the "Look up records" tab

Copyright
---------

Copyright (c) 2021 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

from   commonpy.data_utils import unique, pluralized, flattened
from   commonpy.exceptions import Interrupted
from   commonpy.file_utils import exists, readable
from   commonpy.interrupt import wait, interrupt, interrupted, reset_interrupts
import json
from   pprint import pformat
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
from   pywebio.session import run_js, eval_js
from   sidetrack import set_debug, log
import threading

from   foliage.base_tab import FoliageTab
from   foliage.export import export_records
from   foliage.folio import Folio, RecordKind, RecordIdKind, TypeKind, NAME_KEYS
from   foliage.folio import unique_identifiers
from   foliage.ui import confirm, notify, user_file, stop_processbar
from   foliage.ui import tell_success, tell_warning, tell_failure
from   foliage.ui import note_info, note_warn, note_error


# Tab definition class.
# .............................................................................

class LookupTab(FoliageTab):
    def contents(self):
        return {'title': 'Look up records', 'content': tab_contents()}

    def pin_watchers(self):
        return {}


# Tab body.
# .............................................................................

def tab_contents():
    log(f'generating lookup tab contents')
    return [
        put_grid([[
            put_markdown('Input one or more item barcode, item id, item hrid,'
                         + ' instance id, instance hrid, instance accession'
                         + ' number, loan id, loan hrid, user id, or user barcode'
                         + ' in the field below, or by uploading a text file.'),
            put_button('Upload', outline = True,
                       onclick = lambda: load_file()).style('text-align: right'),
        ]], cell_widths = 'auto 100px'),
        put_textarea('textbox_find', rows = 4),
        put_grid([[
            put_radio('select_kind', inline = True,
                      label = 'Type of record to retrieve:',
                      options = [ ('Item', RecordKind.ITEM, True),
                                  ('Holdings', RecordKind.HOLDINGS),
                                  ('Instance', RecordKind.INSTANCE),
                                  ('Loan', RecordKind.LOAN),
                                  ('User', RecordKind.USER)]),
            put_markdown('_Note: loan records found using item, holdings,'
                         + ' instance or user identifiers are **open** loans'
                         + ' only. Likewise, user records found using'
                         + ' item/holdings/instance/loan id\'s'
                         + ' are based on **open** loans only._'),
        ]], cell_widths = '39% 60%'),
        put_grid([[
            put_radio('show_raw', inline = True,
                      options = [('Summary format', 'summary', True),
                                 ('Raw data format', 'json')],
                      help_text = 'Controls the format of the output produced.'),
            put_checkbox("inventory_api", inline = True,
                         options = [('Use inventory API for items and instances',
                                     True, True)],
                         help_text = 'When deselected, the storage API is used.'),
        ]], cell_widths = '58% 42%'),
        put_row([
            put_button('Look up records', onclick = lambda: do_find()),
            put_text(''),    # Adds a column, pushing next item to the right.
            put_button('Clear', outline = True,
                       onclick = lambda: clear_tab()).style('text-align: right')
        ])
    ]


# Tab implementation.
# .............................................................................

_last_textbox = ''
_last_results = {}
_last_kind = None
_last_inventory_api = True


def clear_tab():
    global _last_textbox
    global _last_inventory_api
    log(f'clearing tab')
    clear('output')
    pin.textbox_find = ''
    pin.inventory_api = [True]
    _last_textbox = ''
    _last_inventory_api = [True]


def stop():
    global _last_textbox
    log(f'stopping')
    interrupt()
    stop_processbar()
    _last_textbox = ''


def load_file():
    log(f'user requesting file upload')
    if (contents := user_file('Upload a file containing identifiers')):
        pin.textbox_find = contents


def do_find():
    global _last_results
    global _last_textbox
    global _last_kind
    global _last_inventory_api
    log(f'do_find invoked')
    # Normally we'd want to find out if they input any identifiers, but I want
    # to detect *any* change to the input box, so this is a lower-level test.
    if not pin.textbox_find.strip():
        note_error('Please input at least one barcode or other id.')
        return
    reuse_results = False
    if (pin.textbox_find == _last_textbox and pin.select_kind == _last_kind
        and pin.inventory_api == _last_inventory_api):
        if user_wants_reuse():
            reuse_results = True
        else:
            _last_results = {}
    _last_textbox = pin.textbox_find
    _last_kind = pin.select_kind
    _last_inventory_api = pin.inventory_api
    reset_interrupts()
    with use_scope('output', clear = True):
        put_markdown(f'_Certain lookups can take a very long time. Please be'
                     + ' patient._').style('color: DarkOrange; margin-left: 17px')
        record_kind = pin.select_kind
        identifiers = unique_identifiers(pin.textbox_find)
        steps = len(identifiers) + 1
        put_grid([[
            put_processbar('bar', init = 1/steps).style('margin-top: 11px; margin-left: 17px'),
            put_button('Stop', outline = True, color = 'danger',
                       onclick = lambda: stop()
                       ).style('text-align: right; margin-left: 17px')
            ]], cell_widths = '85% 15%').style('margin-right: 17px')
        folio = Folio()
        for count, id in enumerate(identifiers, start = 2):
            put_html('<br>')
            try:
                # Figure out what kind of identifier we were given.
                id_kind = folio.record_id_kind(id)
                if id_kind == RecordIdKind.UNKNOWN:
                    tell_failure(f'Unrecognized identifier kind: {id}.')
                    continue

                # Get the record.
                if reuse_results:
                    records = _last_results.get(id)
                else:
                    records = folio.records(id, id_kind, record_kind, pin.inventory_api)
                    _last_results[id] = records
                if interrupted():
                    break
                if not records or len(records) == 0:
                    tell_failure(f'No {record_kind} record(s) found for {id_kind} "{id}".')
                    continue

                # Report the results & how we got them.
                if pin.inventory_api and record_kind in ['item', 'instance']:
                    source = 'inventory'
                else:   # Most records kinds only have storage API endpoints.
                    source = 'storage'
                this = pluralized(record_kind + f' {source} record', records, True)
                how = f'by searching for {id_kind} **{id}**.'
                tell_success(f'Found {this} {how}')
                show_index = (len(records) > 1)
                for index, record in enumerate(records, start = 1):
                    print_record(record, record_kind, id, id_kind,
                                 index, show_index, pin.show_raw == 'json')
                    if interrupted():
                        break
            except Interrupted as ex:
                break
            except Exception as ex:
                tell_failure(f'Error: ' + str(ex))
                return
            finally:
                set_processbar('bar', count/steps)
        stop_processbar()
        put_html('<br>')
        if interrupted():
            tell_warning('**Stopped**.')
        else:
            what = pluralized(f'{record_kind} identifier', identifiers, True)
            put_markdown(f'Finished looking up {what}.').style('text-align: center')
            put_button('Export', outline = True,
                       onclick = lambda: do_export(_last_results, record_kind),
                       ).style('margin-left: 10px; float: right; margin-right: 17px')


def print_record(record, record_kind, identifier, id_kind, index, show_index, show_raw):
    log(f'printing {record_kind} record {record["id"]}')
    if show_index:
        put_markdown(f'{record_kind.title()} record #{index}:')

    if show_raw:
        put_code(pformat(record, indent = 2))
    elif record_kind == 'item':
        # Caution: left-hand values contain nonbreaking spaces (invisible here).
        put_table([
            ['Title'                     , record['title']],
            ['Barcode'                   , record['barcode']],
            ['Call number'               , record['callNumber']],
            [f'{record_kind.title()} id' , record['id']],
            ['Effective location'        , record['effectiveLocation']['name']],
            ['Permanent location'        , record['permanentLocation']['name']],
            ['Status'                    , record['status']['name']],
            ['Tags'                      , ', '.join(t for t in record['tags']['tagList'])],
            ['Notes'                     , '\n'.join(record['notes'])],
            ['HRID'                      , record['hrid']],
            ['Created'                   , record['metadata']['createdDate']],
            ['Updated'                   , record['metadata']['updatedDate']],
        ]).style('font-size: 90%')
    elif record_kind == 'instance':
        # Caution: left-hand values contain nonbreaking spaces (invisible here).
        put_table([
            ['Title'                     , record['title']],
            ['Call number'               , record['classifications'][0]['classificationNumber']],
            [f'{record_kind.title()} id' , record['id']],
            ['Tags'                      , ', '.join(t for t in record['tags']['tagList'])],
            ['HRID'                      , record['hrid']],
            ['Created'                   , record['metadata']['createdDate']],
            ['Updated'                   , record['metadata']['updatedDate']],
        ]).style('font-size: 90%')
    elif record_kind == 'holdings':
        # Caution: left-hand values contain nonbreaking spaces (invisible here).
        put_table([
            [f'{record_kind.title()} id' , record['id']],
            ['HRID'                      , record['hrid']],
            ['Holdings type id'          , record['holdingsTypeId']],
            ['Instance id'               , record['instanceId']],
            ['Created'                   , record['metadata']['createdDate']],
            ['Updated'                   , record['metadata']['updatedDate']],
        ]).style('font-size: 90%')
    elif record_kind == 'user':
        # Caution: left-hand values contain nonbreaking spaces (invisible here).
        put_table([
            ['Username'                  , record['username']],
            ['Barcode'                   , record['barcode']],
            [f'{record_kind.title()} id' , record['id']],
            ['Patron group'              , record['patronGroup']],
            ['Created'                   , record['metadata']['createdDate']],
            ['Updated'                   , record['metadata']['updatedDate']],
        ]).style('font-size: 90%')
    elif record_kind == 'loan':
        put_table([
            [f'{record_kind.title()} id' , record['id']],
            ['User id'                   , record['userId']],
            ['Item id'                   , record['itemId']],
            ['Loan date'                 , record['loanDate']],
            ['Due date'                  , record['dueDate']],
            ['Created'                   , record['metadata']['createdDate']],
            ['Updated'                   , record['metadata']['updatedDate']],
        ]).style('font-size: 90%')


def user_wants_reuse():
    event = threading.Event()
    answer = False

    def clk(val):
        nonlocal answer
        answer = val
        event.set()

    pins = [
        put_text('The list of identifiers and the type of record to retrieve'
                 + ' are unchanged from the previous lookup. Should the results'
                 + ' be reused, or should the identifiers be looked up again?'),
        put_html('<br>'),
        put_buttons([
            {'label': 'Reuse the results', 'value': True},
            {'label': 'Search again', 'value': False, 'color': 'secondary'},
        ], onclick = clk).style('float: left')
    ]
    popup(title = 'Should results be reused?', content = pins, closable = False)

    event.wait()
    close_popup()
    wait(0.5)                           # Give time for popup to go away.

    return answer


def do_export(results, record_kind):
    log(f'exporting {record_kind} {pluralized("record", results, True)}')
    # Results is a dictionary; each value is a list of records. Unwind it.
    all_records = [item for value in results.values() for item in value]
    export_records(all_records, record_kind)
