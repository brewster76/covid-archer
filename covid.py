from requests import get
import json
import pandas as pd
import time
import ftplib
import os
import platform
from Cheetah.Template import Template
from palettable.wesanderson import Zissou_5

import secret

FTP_UPLOAD = True
FILTER_BY_AREAS = True
START_DATE = '2021-06-01'

ENDPOINT = ('https://api.coronavirus.data.gov.uk/v2/data?'
            'areaType=overview'
            '&metric=newDeaths28DaysByPublishDate'
            '&metric=newCasesByPublishDate'
            '&metric=hospitalCases'
            '&format=json'
            )

TEMPLATE_FILENAME = 'covid.html.tmpl'
HTML_FILENAME = 'covid.html'
WORKING_DIRECTORY = '/home/pi/covid'

PI_MACHINES = ['armv7l', 'armv6l']

y1_color = Zissou_5.hex_colors[0]
y2_color = Zissou_5.hex_colors[2]
y3_color = Zissou_5.hex_colors[4]

def am_i_pi():
    return platform.machine() in PI_MACHINES


pickle_file_name = time.strftime('national-%Y-%m-%d.pkl')

if am_i_pi():
    print(f'Changing to {WORKING_DIRECTORY}')
    os.chdir(WORKING_DIRECTORY)

#
# Data download
#

print("Downloading new data")
response = get(ENDPOINT, timeout=10)

if response.status_code >= 400:
    raise RuntimeError(f'Request failed: {response.text}')

data = json.loads(response.text)['body']

df = pd.json_normalize(data)

# Convert date from string to datetime
df['date'] = pd.to_datetime(df['date'], format='%Y-%m-%d')

# Exclude anything before START_DATE
filtered_df = df[df['date'] >= START_DATE]


#
# Cases and deaths chart
#
def cases_and_deaths():
    my_chart = {'type': 'line', 'data': {'labels': [], 'datasets': []}, 'options': {}}

    for d in reversed(filtered_df.date):
        my_chart['data']['labels'].append(d.strftime('%d-%b'))

    cases_list = list(reversed(filtered_df['newCasesByPublishDate'].rolling(7, center=True).mean().round(1).tolist()))
    my_chart['data']['datasets'].append({'label': 'Cases',
                                         'data': cases_list,
                                         'lineTension': 0, 'fill': False,
                                         'borderColor': y1_color, 'backgroundColor': y1_color,
                                         'yAxisID': 'A'})

    deaths_list = list(
        reversed(filtered_df['newDeaths28DaysByPublishDate'].rolling(7, center=True).mean().round(1).tolist()))
    my_chart['data']['datasets'].append({'label': 'Deaths',
                                         'data': deaths_list,
                                         'lineTension': 0, 'fill': False,
                                         'borderColor': y2_color, 'backgroundColor': y2_color,
                                         'yAxisID': 'B'})

    my_chart['options']['scales'] = {'yAxes': [{'id': 'A', 'type': 'linear', 'position': 'left',
                                                'gridLines': {'display': False},
                                                'ticks': {'beginAtZero': True, 'fontColor': y1_color},
                                                'scaleLabel': {'display': True, 'labelString': 'Cases',
                                                               'fontColor': y1_color}},
                                               {'id': 'B', 'type': 'linear', 'position': 'right',
                                                'gridLines': {'display': False},
                                                'ticks': {'beginAtZero': True, 'fontColor': y2_color},
                                                'scaleLabel': {'display': True, 'labelString': 'Deaths',
                                                               'fontColor': y2_color}}]}

    my_chart['options']['legend'] = {'display': False}

    return "var casesChart = new Chart(ctx, %s );" % json.dumps(my_chart)


def hospital():
    my_chart = {'type': 'line', 'data': {'labels': [], 'datasets': []}, 'options': {}}

    for d in reversed(filtered_df.date):
        my_chart['data']['labels'].append(d.strftime('%d-%b'))

    cases_list = list(reversed(filtered_df['newCasesByPublishDate'].rolling(7, center=True).mean().round(1).tolist()))
    my_chart['data']['datasets'].append({'label': 'Cases',
                                         'data': cases_list,
                                         'lineTension': 0, 'fill': False,
                                         'borderColor': y1_color, 'backgroundColor': y1_color,
                                         'yAxisID': 'A'})

    hospital_list = list(reversed(filtered_df['hospitalCases'].rolling(7, center=True).mean().round(1).tolist()))
    my_chart['data']['datasets'].append({'label': 'Deaths',
                                         'data': hospital_list,
                                         'lineTension': 0, 'fill': False,
                                         'borderColor': y3_color, 'backgroundColor': y3_color,
                                         'yAxisID': 'B'})

    my_chart['options']['scales'] = {'yAxes': [{'id': 'A', 'type': 'linear', 'position': 'left',
                                                'gridLines': {'display': False},
                                                'ticks': {'beginAtZero': True, 'fontColor': y1_color},
                                                'scaleLabel': {'display': True, 'labelString': 'Cases',
                                                               'fontColor': y1_color}},
                                               {'id': 'B', 'type': 'linear', 'position': 'right',
                                                'gridLines': {'display': False},
                                                'ticks': {'beginAtZero': True, 'fontColor': y3_color},
                                                'scaleLabel': {'display': True, 'labelString': 'In Hospital',
                                                               'fontColor': y3_color}}]}
    my_chart['options']['legend'] = {'display': False}

    return "var hospitalChart = new Chart(ctx, %s );" % json.dumps(my_chart)


namespace = {'cases_chart': cases_and_deaths(), 'hospital_chart': hospital(),
             'updated': time.strftime('%H:%M'),
             'data_date': filtered_df.date[0].strftime('%A %d %B %Y')}

with open(TEMPLATE_FILENAME, 'r') as template_file:
    with open(HTML_FILENAME, 'w') as html_file:
        print(f'Writing html file: {HTML_FILENAME}')
        html_file.write(str(Template(template_file.read(), searchList=[namespace])))

#
# FTP upload
#
if FTP_UPLOAD:
    session = ftplib.FTP(secret.SITE, secret.USER_NAME, secret.PASSWORD)
    session.cwd(secret.ROOT_DIR)

    print(f'Uploading {HTML_FILENAME}')
    with open(HTML_FILENAME, 'rb') as html_file:
        print(session.storbinary(f'STOR {HTML_FILENAME}', html_file))
    session.quit()
