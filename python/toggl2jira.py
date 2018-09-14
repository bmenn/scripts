#!/usr/bin/env python3
import configparser
import os
import re
import json
import requests
import datetime
import time
import arrow

CONFIG = configparser.ConfigParser()
CONFIG.read(os.path.expanduser('~/.atlassianrc'))

JIRA_API_KEY = CONFIG['atlassian']['api_token']
JIRA_USER = CONFIG['atlassian']['user']
JIRA_AUTH = (JIRA_USER, JIRA_API_KEY)
JIRA_URL = CONFIG['atlassian']['domain']
JIRA_API = 'rest/api/3'
JIRA_AUTH = (R, JIRA_API_KEY)

TOGGL_API_KEY = CONFIG['toggl']['api_token']
TOGGL_AUTH = (TOGGL_API_KEY, 'api_token')
TOGGL_URL = 'https://www.toggl.com'
TOGGL_STD_API = 'api/v8'
TOGGL_REPORT_API = 'reports/api/v2'
JIRA_LOGGED = 'jira-logged'
IS_LOGGED_REGEX = re.compile(JIRA_LOGGED)
ISSUE_REGEX = re.compile(CONFIG['toggl']['issue_regex'])


def is_logged(entry):
    return any([IS_LOGGED_REGEX.match(t) for t in entry['tags']])


def mark_logged(entries):
    if len(entries) == 0:
        return
    url = (
        '/'.join([
            TOGGL_URL,
            TOGGL_STD_API,
            'time_entries',
            ','.join([str(e['entry_id']) for e in entries])
        ])
    )
    data = json.dumps({
        'time_entry': {
            'tags': [JIRA_LOGGED],
            'tag_action': 'add'
        },
    })

    response = requests.put(url, data=data, auth=TOGGL_AUTH)
    response.raise_for_status()


def secondsSpent(start, end):
    stime = arrow.get(start)
    etime = arrow.get(end)

    return (etime - stime).total_seconds()


def log_to_jira(ticket, entries):
    url = (
        '/'.join([
            JIRA_URL,
            JIRA_API,
            'issue',
            ticket,
            'worklog'
        ])
    )
    for e in entries:
        data = json.dumps({
            'started': arrow.get(e['start']).format('YYYY-MM-DDTHH:mm:ss.SSSZ'),
            'timeSpentSeconds': secondsSpent(e['start'], e['end'])
        })
        response = requests.post(url, data=data, auth=JIRA_AUTH,
                                 headers={'content-type': 'application/json'})
        response.raise_for_status()


def process_report_page(page_data, ticket_work_log):
    for entry in page_data:
        if is_logged(entry):
            continue

        match_issue = ISSUE_REGEX.match(entry['description'])
        if match_issue:
            t = match_issue[0]
            try:
                ticket_work_log[t].append({
                    'entry_id': entry['id'],
                    'start': entry['start'],
                    'end': entry['end'],
                })
            except KeyError:
                ticket_work_log[t] = [{
                    'entry_id': entry['id'],
                    'start': entry['start'],
                    'end': entry['end'],
                }]

    return ticket_work_log


def main():
    response = requests.get('/'.join([TOGGL_URL, TOGGL_STD_API, 'workspaces']),
                            auth=TOGGL_AUTH)

    workspace_ids = {w['name']: w['id'] for w in response.json()}

    workspace = workspace_ids[CONFIG['toggl']['workspace']]

    response = requests.get(
        '/'.join([TOGGL_URL, TOGGL_STD_API, 'workspaces', str(workspace), 'tags']),
        auth=TOGGL_AUTH
    )

    searchback_date = datetime.date.today() - datetime.timedelta(days=30)
    url_params = {
        'page': 1,
        'workspace_id': workspace,
        'user_agent': 'test_api',
        'since': searchback_date.isoformat(),
    }

    url = (
        '/'.join([TOGGL_URL, TOGGL_REPORT_API, 'details?']) +
        '&'.join('='.join((str(k), str(v))) for k, v in url_params.items())
    )
    response = requests.get(url, auth=TOGGL_AUTH)
    response.raise_for_status()

    response_json = response.json()
    ticket_work_log = {}
    while len(response_json['data']) > 0:
        ticket_work_log = process_report_page(response_json['data'],
                                              ticket_work_log)

        url_params['page'] += 1
        url = (
            '/'.join([TOGGL_URL, TOGGL_REPORT_API, 'details?']) +
            '&'.join('='.join((str(k), str(v))) for k, v in url_params.items())
        )
        response = requests.get(url, auth=TOGGL_AUTH)
        response.raise_for_status()
        response_json = response.json()

    ticket_work_log = process_report_page(response_json['data'],
                                          ticket_work_log)

    tickets_to_update = len(ticket_work_log)
    for i, (ticket, entries) in enumerate(ticket_work_log.items()):
        print('Updating %s with %d entries (%d/%d)' %
              (ticket, len(entries), i, tickets_to_update))
        log_to_jira(ticket, entries)
        mark_logged(entries)

if __name__ == '__main__':
    main()
