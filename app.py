import os
import math
import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import json
import redis
import subprocess
import requests
import pytz
import logging
from flask_sslify import SSLify
from dash import dcc, html, Input, Output, dash_table, State
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify, session, request
from flask_session import Session
from datetime import datetime, timedelta
from utils import generate_secret_key

logging.getLogger().setLevel(logging.INFO)

# Set up Redis connection
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
client = redis.Redis.from_url(redis_url)

COLORS = 1
DEFAULT_LANGUAGE = 'pt-br'
SECRET_KEY = generate_secret_key()
CALL_API_MINUTES = int(os.getenv('CALL_API_MINUTES', 15))
FLASK_ENV = os.getenv('FLASK_ENV')

dict_config = {
    1: {'backgroundColor': '#0E0F0E', 'fontColor': 'white', 'map_style': 'carto-darkmatter', 'font-family': 'Georgia, serif'},
    2: {'backgroundColor': 'white', 'fontColor': 'black', 'map_style': 'carto-positron', 'font-family': 'Georgia, serif'}
}

backgroundColor = dict_config[COLORS]["backgroundColor"]
fontColor = dict_config[COLORS]["fontColor"]
map_style = dict_config[COLORS]["map_style"]
font_family = dict_config[COLORS]["font-family"]

dict_columns = {
    'Vacancies': {'pt-br': 'Vagas', 'en': 'Vacancies'},
    'Distance': {'pt-br': 'Distancia', 'en': 'Distance'},
    'Hide': {'pt-br': 'Esconder', 'en': 'Hide'},
    'Yes': {'pt-br': 'Sim', 'en': 'Yes'},
    'No': {'pt-br': 'Não', 'en': 'No'},
    'All': {'pt-br': 'Todos', 'en': 'All'},
    'Pet': {'pt-br': 'Animais', 'en': 'Pet'},
    'AllCities': {'pt-br': 'Todas', 'en': 'All'},
    'City': {'pt-br': 'Cidade', 'en': 'City'},
    'Shelter': {'pt-br': 'Abrigo', 'en': 'Shelter'},
    'People': {'pt-br': 'Pessoas', 'en': 'People'},
    'UpdatedAt': {'pt-br': 'Atualizado em', 'en': 'Updated At'},
    'Address': {'pt-br': 'Endereço', 'en': 'Address'},
    'Capacity': {'pt-br': 'Capacidade', 'en': 'Capacity'},
    'Availability': {'pt-br': 'Disponibilidade', 'en': 'Availability'},
    'VerificationStatus': {'pt-br': 'Verificado', 'en': 'Verified'},
    'PetFriendly': {'pt-br': 'Aceita Animais', 'en': 'Pet Friendly'},
    'AmountOfShelters': {'pt-br': 'Abrigos', 'en': 'Shelters'},
    'AmountOfPeopleSheltered': {'pt-br': 'Pessoas Abrigadas', 'en': 'People Sheltered'},
    'SheltersVerified': {'pt-br': 'Verificados', 'en': 'Verified'},
    'SheltersNotVerified': {'pt-br': 'Nāo Verificados', 'en': 'Not Verified'},
    'Search': {'pt-br': 'Buscar por abrigo ou endereço', 'en': 'Search for shelter or address'},
    'AvailabilityStatus': {
        'Available': {'statusId': 1, 'pt-br': 'Disponível', 'en': 'Available', 'color': '#2ECC40'},
        'Check': {'statusId': 2, 'pt-br': 'Consultar', 'en': 'Check', 'color': '#00BFFF'},
        'Crowded': {'statusId': 3, 'pt-br': 'Cheio', 'en': 'Crowded', 'color': '#FFB347'},
        'Full': {'statusId': 4, 'pt-br': 'Lotado', 'en': 'Full', 'color': '#FF6347'},
        'Location': {'statusId': 5, 'pt-br': 'Sua Localização', 'en': 'Your Location', 'color': fontColor},
    }
}

dict_availabilityStatus = dict_columns['AvailabilityStatus']

dict_rename = {
    'availability': 'availability',
    'link': 'link',
}

def get_data():
    shelter_data = client.get('shelters')
    if shelter_data:
        return json.loads(shelter_data)
    else:
        with open('shelters.json', 'r') as file:
            return json.load(file)

def distance_haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371

    distance = c * r
    if math.isnan(distance):
        return ["", distance]
    else:
        return [f"{round(distance, 1)} Km", distance]

def map_availability(row, key):
    if pd.isnull(row['capacity']) or pd.isnull(row['shelteredPeople']):
        status = 'Check'
    elif row['shelteredPeople'] > row['capacity']:
        status = 'Full'
    elif row['shelteredPeople'] == row['capacity']:
        status = 'Crowded'
    else:
        status = 'Available'
    
    return dict_availabilityStatus[status][key]

def create_link(row):
    icons = f"{row['pet_icon']}"
    return f"{icons} [{row['name']}](https://sos-rs.com/abrigo/{row['id']})"

def format_date(data_original):
    data_datetime = pd.to_datetime(data_original)
    return data_datetime.strftime("%d/%m/%Y %H:%M:%S")

def calculate_vacancies(row):
    if row['capacity'] >= 0 and row['shelteredPeople'] >= 0:
        return row['capacity'] - row['shelteredPeople']
    else:
        return "-"

def get_formated_data():
    df = pd.json_normalize(get_data())
    df['pet_icon'] = df['petFriendly'].apply(lambda x: '🐾' if x else '')
    df['verification_icon'] = df['verified'].apply(lambda x: '✔️' if x else '❌')
    df['capacity_info'] = df.apply(lambda row: f"{int(row['shelteredPeople']) if pd.notnull(row['shelteredPeople']) else '-'}/{int(row['capacity']) if pd.notnull(row['capacity']) else '-'}", axis=1)
    df['vacancies'] = df.apply(calculate_vacancies, axis=1)
    df['link'] = df.apply(create_link, axis=1)# Creates Markdown column with the source API url
    df['updatedAt'] = df['updatedAt'].apply(format_date)
    df = df.sort_values(by='updatedAt', ascending=False)
    df['availability'] = df.apply(lambda row: map_availability(row, 'statusId'), axis=1)
    return df

def data_cities(df, language):
    df['city'] = df['city'].fillna('').astype(str)
    cities = df['city'].unique()
    city_options = [{'label': city, 'value': city} for city in cities if city is not None]
    city_options.insert(0, {'label': dict_columns['AllCities'][language], 'value': dict_columns['AllCities'][language]})
    city_options = sorted(city_options, key=lambda x: x['label'])
    return city_options

def update_shelter_data():
    logging.info("Running update_shelter_data")
    try:
        result = subprocess.run(['python', 'get_api_data.py'], capture_output=True, text=True)
        if result.returncode != 0:
            logging.error(f"Error updating data: {result.stderr}")
        else:
            current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            logging.info(f"Result of update: {result.stdout}")
            client.set('last_update', current_time)
            logging.info(f"Data updated successfully {current_time} (UTC)")
    except Exception as e:
        logging.error(f"Exception during data update: {e}")

def get_last_update_time():
    last_update = client.get('last_update')
    if last_update:
        last_update_utc = datetime.strptime(last_update.decode('utf-8'), '%Y-%m-%d %H:%M:%S')
        timezone = session.get('timezone', 'UTC')
        local_tz = pytz.timezone(timezone)
        last_update_local = last_update_utc.replace(tzinfo=pytz.utc).astimezone(local_tz)
        return last_update_local.strftime('%Y-%m-%d %H:%M:%S')
    return ''

def get_user_language_and_location():
    try:
        if FLASK_ENV == 'production':
            ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0]
        else:
            ip = "193.19.205.155"

        cached_response = client.get(f"user_location:{ip}")
        if cached_response:
            logging.info(f"{datetime.utcnow()}:{ ip = }is cached")
            response = json.loads(cached_response)
        else:
            if FLASK_ENV == 'production':
                response = requests.get(f'https://ipinfo.io/{ip}/json').json()
                logging.info(f"{datetime.utcnow()}:{ ip = }{response=}")
            else:
                response = {'ip': '193.19.205.155','city': 'Barra do Ribeiro','region': 'São Paulo','country': 'BR','loc': '-30.300278,-51.30477','timezone': 'America/Sao_Paulo'}
            client.setex(f"user_location:{ip}", timedelta(hours=24), json.dumps(response))
            logging.info(f"{datetime.utcnow()}:{ ip = }added to Redis.")

        loc = response.get('loc')
        country = response.get('country')
        city = response.get('city')
        timezone = response.get('timezone')

        if loc:
            lat, lon = loc.split(',')
            return ('pt-br' if country == 'BR' else 'en', float(lat), float(lon), city, timezone)
        else:
            return DEFAULT_LANGUAGE, None, None, '', 'America/Sao_Paulo'
    except Exception as e:
        logging.error(f"Error determining user location: {e}")
    if FLASK_ENV == 'production':
        return DEFAULT_LANGUAGE, None, None, '', 'America/Sao_Paulo'

df = get_formated_data()

server = Flask(__name__)
server.config['SECRET_KEY'] = SECRET_KEY
server.config['SESSION_TYPE'] = 'redis'
server.config['SESSION_PERMANENT'] = False
server.config['SESSION_USE_SIGNER'] = True
server.config['SESSION_KEY_PREFIX'] = 'session:'
server.config['SESSION_REDIS'] = redis.from_url(redis_url)
server.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=60)
Session(server)

app = dash.Dash(__name__, server=server, external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True)

app.index_string = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Abrigos - Rio Grande do Sul</title>
    <link rel="apple-touch-icon" sizes="180x180" href="/assets/favicon_io/apple-touch-icon.png">
    <link rel="icon" type="image/png" sizes="32x32" href="/assets/favicon_io/favicon-32x32.png">
    <link rel="icon" type="image/png" sizes="16x16" href="/assets/favicon_io/favicon-16x16.png">
    <link rel="manifest" href="/assets/favicon_io/site.webmanifest">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    {%favicon%}
    {%css%}
</head>
<body>
    {%app_entry%}
    <footer>
        {%config%}
        {%scripts%}
        {%renderer%}
    </footer>
</body>
</html>
'''

if 'DYNO' in os.environ:  # Only trigger SSLify if on Heroku
    sslify = SSLify(server)

@server.before_request
def before_request():
    session.permanent = True
    if 'language' not in session or 'lat' not in session or 'lon' not in session:
        user_language, lat, lon, city, timezone = get_user_language_and_location()
        session['language'] = user_language
        session['lat'] = lat
        session['lon'] = lon
        session['city'] = city
        session['timezone'] = timezone
        session['initialized'] = True
        logging.info(f"Session - {datetime.utcnow()}: {session['language']}, {session['lat']}, {session['lon']}, {session['city']}, {session['timezone']}")

scheduler = BackgroundScheduler()
scheduler.add_job(update_shelter_data, 'interval', minutes=CALL_API_MINUTES, id='update_job')
scheduler.start()

@server.route('/update-data', methods=['GET'])
def update_data():
    try:
        update_shelter_data()
        return jsonify({"message": "Data update triggered"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@server.route('/update-interval', methods=['POST'])
def update_interval():
    new_interval = request.json.get('interval', CALL_API_MINUTES)
    scheduler.reschedule_job('update_job', trigger='interval', minutes=new_interval)
    return jsonify({"message": "Interval updated", "new_interval": new_interval})


@server.route('/pt-br')
def pt_br():
    session['language'] = 'pt-br'
    return app.index()

@server.route('/en')
def en():
    session['language'] = 'en'
    return app.index()

app.layout = dbc.Container([
    #Language
    dbc.Row([
        dbc.Col(html.Div([
            html.A([
                html.Img(src='https://cdn-icons-png.flaticon.com/128/197/197386.png', style={'cursor': 'pointer', 'width': '25px', 'height': '25px', 'margin-right': '8px'}),
            ], title="brazil icons", id='pt-br', n_clicks=0),
            html.A([
                html.Img(src='https://cdn-icons-png.flaticon.com/128/197/197484.png', style={'cursor': 'pointer', 'width': '25px', 'height': '25px', 'margin-left': '8px'}),
            ], title="usa icons", id='en', n_clicks=0),
        ]), width="auto"),
    ], className="justify-content-center",
    style={'padding': '10px'}),
    #Title
    dbc.Row([
        dbc.Col(html.H1(id='title', style={'color': fontColor, 'textAlign': 'center', 'font-family': 'Georgia, serif'}), width=12)
    ], style={'textAlign': 'center'}),
    #Last Update
    dbc.Row([
        dbc.Col(html.Div(id='last-update-div'), width=12)
    ], style={'textAlign': 'center', 'margin-bottom': '5px'}),
    #Search
    dbc.Row([
        dbc.Col(dcc.Input(
            id='search-filter',
            type='text',
            className='responsive-input', 
            style={'textAlign': 'center'}
        ))
    ], style={'textAlign': 'center', 'margin-bottom': '4px'}),
    #Filters
    dbc.Row([
        dbc.Col([
            html.Label(id='city-label', style={'color': fontColor}),
            dcc.Dropdown(
                id='city-filter',
                multi=True,
                clearable=True,
                style={'color': 'black'}
            )
        ], xs=12, sm=12, md=6, lg=3, className="mb-1"), 
        dbc.Col([
            html.Label(id='availability-label', style={'color': fontColor}),
            dcc.Dropdown(
                id='availability-filter',
                multi=True,
                clearable=True,
                style={'color': 'black'}
            )
        ], xs=12, sm=12, md=6, lg=3, className="mb-1"),
        dbc.Col([
            html.Label(id='verification-label', style={'color': fontColor}),
            dcc.Dropdown(
                id='verification-filter',
                clearable=False,
                style={'color': 'black'}
            )
        ], xs=12, sm=12, md=6, lg=3, className="mb-1"),
        dbc.Col([
            html.Label(id='pet-label', style={'color': fontColor}),
            dcc.Dropdown(
                id='pet-filter',
                clearable=False,
                style={'color': 'black'}
            )
        ], xs=12, sm=12, md=6, lg=3, className="mb-1"),
    ], style={'backgroundColor': backgroundColor, 'margin-bottom': '4px'}),
    # Graphs
    dbc.Row([
       dbc.Col([
            dbc.Button(id="hide-info"),
            dbc.Row(dbc.Col(html.Div(id='empty-div'))),
            dbc.Row(dbc.Col(id='num-shelters-div')),
            dbc.Row(dbc.Col(id='verified-shelters-div')),
            dbc.Row(dbc.Col(id='not-verified-shelters-div')),
            dbc.Row(dbc.Col(id='pet-friendly-shelters-div')),
            dbc.Row(dbc.Col(id='total-people-div')),
        ], xs=12, sm=12, md=6, lg=3, className="mb-2"),
        dbc.Col([
            dbc.Button(id="hide-map"),
            dcc.Graph(id='map', style={'display': 'block'})
        ], xs=12, sm=12, md=6, lg=6, className="mb-2"),
        dbc.Col([
            dbc.Button(id="hide-city-distribution"),
            dcc.Graph(id='city-distribution', style={'display': 'block'})
        ], xs=12, sm=12, md=6, lg=3, className="mb-2"),
        ], style={'backgroundColor': backgroundColor, 'textAlign': 'center'} 
    ),
    #Table
    dbc.Row([
        dbc.Col(html.Div(id='shelter-table-div'), width=12)
    ])
], fluid=True, style={'backgroundColor': backgroundColor})

@app.callback(
    Output('empty-div', 'style'),
    Output('num-shelters-div', 'style'),
    Output('verified-shelters-div', 'style'),
    Output('not-verified-shelters-div', 'style'),
    Output('pet-friendly-shelters-div', 'style'),
    Output('total-people-div', 'style'),
    Input('hide-info', 'n_clicks'),
    State('num-shelters-div', 'style'),
    State('verified-shelters-div', 'style'),
    State('not-verified-shelters-div', 'style'),
    State('pet-friendly-shelters-div', 'style'),
    State('total-people-div', 'style'),
    prevent_initial_call=True
)
def hide_info(n_clicks, num_style, verified_style, not_verified_style, pet_friendly_style, total_people_style):
    if num_style is None or num_style.get('display', 'block') == 'block':
        new_style = {'display': 'none'}
    else:
        new_style = {'display': 'block'}
    return new_style, new_style, new_style, new_style, new_style, new_style

@app.callback(
    Output('map', 'style'),
    Input('hide-map', 'n_clicks'),
    State('map', 'style'),
    prevent_initial_call=True
)
def hide_map(n_clicks, current_style):
    if current_style is None or current_style.get('display', 'block') == 'block':
        return {'display': 'none'}
    return {'display': 'block'}

@app.callback(
    Output('city-distribution', 'style'),
    Input('hide-city-distribution', 'n_clicks'),
    State('city-distribution', 'style'),
    prevent_initial_call=True
)
def hide_city_distribution(n_clicks, current_style):
    if current_style is None or current_style.get('display', 'block') == 'block':
        return {'display': 'none'}
    return {'display': 'block'}

@app.callback(
    [Output('title', 'children'),
     Output('search-filter', 'placeholder'),
     Output('city-label', 'children'),
     Output('city-filter', 'options'),
     Output('city-filter', 'value'),
     Output('availability-label', 'children'),
     Output('availability-filter', 'options'),
     Output('availability-filter', 'value'),
     Output('verification-label', 'children'),
     Output('verification-filter', 'options'),
     Output('verification-filter', 'value'),
     Output('pet-label', 'children'),
     Output('pet-filter', 'options'),
     Output('pet-filter', 'value'),
     Output('hide-info', 'children'),
     Output('hide-map', 'children'),
     Output('hide-city-distribution', 'children'),
     Output('last-update-div', 'children')],
    [Input('pt-br', 'n_clicks'),
     Input('en', 'n_clicks')],
    [State('search-filter', 'placeholder'),
     State('city-label', 'children'),
     State('city-filter', 'options'),
     State('city-filter', 'value'),
     State('availability-label', 'children'),
     State('availability-filter', 'options'),
     State('availability-filter', 'value'),
     State('verification-label', 'children'),
     State('verification-filter', 'options'),
     State('verification-filter', 'value'),
     State('pet-label', 'children'),
     State('pet-filter', 'options'),
     State('pet-filter', 'value')]
)
def update_language(pt_clicks, en_clicks, search_placeholder, city_label, city_options, city_values, availability_label, availability_options, availability_values, verification_label, verification_options, verification_values, pet_label, pet_options, pet_values):
    language = session.get('language', DEFAULT_LANGUAGE)
    if en_clicks and (not pt_clicks or en_clicks > pt_clicks):
        language = 'en'
    elif pt_clicks and (not en_clicks or pt_clicks > en_clicks):
        language = 'pt-br'
    
    city_options = data_cities(df, language)
    last_update_time = f"{dict_columns['UpdatedAt'][language]}: {get_last_update_time()}"

    availability_options = [
        {'label': dict_columns['All'][language], 'value': dict_columns['All'][language]},
        {'label': dict_availabilityStatus['Available'][language], 'value': dict_availabilityStatus['Available']['statusId']},
        {'label': dict_availabilityStatus['Check'][language], 'value': dict_availabilityStatus['Check']['statusId']},
        {'label': dict_availabilityStatus['Crowded'][language], 'value': dict_availabilityStatus['Crowded']['statusId']},
        {'label': dict_availabilityStatus['Full'][language], 'value': dict_availabilityStatus['Full']['statusId']},
    ]
    
    availability_values = [
        dict_availabilityStatus['Available']['statusId'],
        dict_availabilityStatus['Check']['statusId']
    ]

    simple_options = [
        {'label': dict_columns['Yes'][language], 'value': True},
        {'label': dict_columns['No'][language], 'value': False},
        {'label': dict_columns['All'][language], 'value': dict_columns['All'][language]}
    ]
    
    verification_options = simple_options
    pet_options = simple_options

    city_values = dict_columns['AllCities'][language]
    
    simple_values = dict_columns['All'][language]
    verification_values = simple_values
    pet_values = simple_values
    
    return (f"{dict_columns['Shelter'][language]}s - Rio Grande do Sul",
            dict_columns['Search'][language],
            dict_columns['City'][language]+':',
            city_options,
            city_values,
            dict_columns['Availability'][language]+':',
            availability_options,
            availability_values,
            dict_columns['VerificationStatus'][language]+':',
            verification_options,
            verification_values,
            dict_columns['Pet'][language]+':',
            pet_options,
            pet_values,
            dict_columns['Hide'][language],
            dict_columns['Hide'][language],
            dict_columns['Hide'][language],
            last_update_time)

@app.callback(
    [Output('map', 'figure'),
     Output('city-distribution', 'figure'),
     Output('num-shelters-div', 'children'),
     Output('total-people-div', 'children'),
     Output('verified-shelters-div', 'children'),
     Output('not-verified-shelters-div', 'children'),
     Output('pet-friendly-shelters-div', 'children'),
     Output('shelter-table-div', 'children')],
    [Input('search-filter', 'value'),
     Input('city-filter', 'value'),
     Input('verification-filter', 'value'),
     Input('pet-filter', 'value'),
     Input('availability-filter', 'value'),
     Input('pt-br', 'n_clicks'),
     Input('en', 'n_clicks')],
    [State('map', 'figure')]
)
def update_data(search, city, verification, pet, availability, pt_clicks, en_clicks, map_figure):
    APP_TABLE_PAGE_SIZE =  int(os.getenv('APP_TABLE_PAGE_SIZE',25))
    language = session.get('language')
    if en_clicks and (not pt_clicks or en_clicks > pt_clicks):
        language = 'en'
    elif pt_clicks and (not en_clicks or pt_clicks > en_clicks):
        language = 'pt-br'

    filtered_df = get_formated_data()
    
    if search:
        search = search.lower()
        filtered_df = filtered_df[
            filtered_df.apply(
                lambda row: row.astype(str).str.lower().str.contains(search).any(), axis=1
            )
        ]

    if dict_columns['AllCities'][language] not in city and len(city) > 0:
        filtered_df = filtered_df[filtered_df['city'].isin(city)]

    if dict_columns['All'][language] not in availability and len(availability) > 0:
        filtered_df = filtered_df[filtered_df['availability'].isin(availability)]
    
    if dict_columns['All'][language] != verification:
        filtered_df = filtered_df[filtered_df['verified'] == verification]

    if dict_columns['All'][language] != pet:
        filtered_df = filtered_df[filtered_df['petFriendly'] == pet]
    
    session_lat = session.get('lat')
    session_lon = session.get('lon')
    session_city = session.get('city')

    filtered_df['availabilityDescription'] = filtered_df.apply(lambda row: map_availability(row, language), axis=1)

    if filtered_df.shape[0] == 0:
        filtered_df['distance_km'] = []
        filtered_df['distance_km2'] = []
    else:
        filtered_df[['distance_km', 'distance_km2']] = filtered_df.apply(lambda row: distance_haversine(row['latitude'], row['longitude'], session_lat, session_lon), axis=1, result_type='expand')

    filtered_df = filtered_df.sort_values(by=['distance_km2'], ascending=[True], na_position='last')
    
    # Text
    tex_style = {'color': fontColor, 'fontWeight': 'bold'}
    num_shelters = html.P(f"{dict_columns['AmountOfShelters'][language]}: {len(filtered_df)}", style=tex_style)
    total_people = html.P(f"{dict_columns['AmountOfPeopleSheltered'][language]}: {int(filtered_df['shelteredPeople'].sum())}", style=tex_style)
    verified_shelters = html.P(f"{dict_columns['SheltersVerified'][language]}: {len(filtered_df[filtered_df['verified']])}", style=tex_style)
    not_verified_shelters = html.P(f"{dict_columns['SheltersNotVerified'][language]}: {len(filtered_df[~filtered_df['verified']])}", style=tex_style)
    pet_friendly_shelters = html.P(f"{dict_columns['PetFriendly'][language]}: {filtered_df['petFriendly'].sum()}", style=tex_style)

    # Map Graph
    new_point = pd.DataFrame({
        'latitude': [session_lat],
        'longitude': [session_lon],
        'name': dict_availabilityStatus['Location'][language],
        'city': session_city,
        'capacity': '',
        'shelteredPeople': '',
        'availabilityDescription': dict_availabilityStatus['Location'][language]
    })

    labels = {
        'latitude': 'Latitude',
        'longitude': 'Longitude',
        'name': dict_columns['Shelter'][language],
        'city': dict_columns['City'][language],
        'capacity': dict_columns['Capacity'][language],
        'shelteredPeople': dict_columns['AmountOfPeopleSheltered'][language],
        'availabilityDescription': dict_columns['Availability'][language]
    }

    hover_columns = ['city', 'capacity', 'shelteredPeople', 'availabilityDescription']

    map_df = pd.concat([filtered_df, new_point], ignore_index=True)
    map_df[hover_columns] = map_df[hover_columns].fillna("")

    color_availability = {
        dict_availabilityStatus['Available'][language]: dict_availabilityStatus['Available']['color'],
        dict_availabilityStatus['Check'][language]: dict_availabilityStatus['Check']['color'],
        dict_availabilityStatus['Crowded'][language]: dict_availabilityStatus['Crowded']['color'],
        dict_availabilityStatus['Full'][language]: dict_availabilityStatus['Full']['color'],
        dict_availabilityStatus['Location'][language]: dict_availabilityStatus['Location']['color']
    }

    fig = px.scatter_mapbox(
        map_df,
        lat="latitude",
        lon="longitude",
        hover_name="name",
        hover_data=hover_columns,
        color="availabilityDescription",
        color_discrete_map=color_availability,
        labels=labels,
        zoom=9,
    )

    fig.update_traces(marker=dict(size=12))

    cities = df['city'].unique()
    cities_lower = [city.lower() for city in cities if city is not None]

    # Set center based in the user location 
    if session_city.lower() in cities_lower:
        map_center = {"lat": session_lat, "lon": session_lon}
    else:
        map_center = {"lat": -30.033056, "lon": -51.230000}

    fig.update_layout(
        mapbox_center=map_center,
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        paper_bgcolor=backgroundColor,
        mapbox_style=map_style,
        legend=dict(
            x=0,
            y=1,
            title_font_family="Times New Roman",
            font=dict(
                family="Courier",
                size=12,
                color=fontColor
            ),
            title_text=""
        )
    )

    # Pie Graph
    pie_df = map_df.loc[map_df['availabilityDescription'] != dict_availabilityStatus['Location'][language]]

    category_counts = pie_df['availabilityDescription'].value_counts().reset_index()
    category_counts.columns = ['availabilityDescription', 'count']

    city_distribution = px.pie(
        category_counts,
        names='availabilityDescription',
        values='count',
        hole=0.25,
        color='availabilityDescription',
        color_discrete_map=color_availability,
    )

    city_distribution.update_layout(
        title_font_color=fontColor,
        font_color=fontColor,
        paper_bgcolor=backgroundColor,
        plot_bgcolor=fontColor,
    )

    city_distribution.update_traces(
        hovertemplate='%{label}: %{value} <extra></extra>'
    )

    # Table
    shelter_table = dash_table.DataTable(
        columns=[
            {"name": f"{dict_columns['Shelter'][language]}", "id": "link", "presentation": "markdown"},
            {"name": f"{dict_columns['Address'][language]}", "id": "address"},
            {"name": f"{dict_columns['Capacity'][language]}", "id": "capacity_info", "sort_as_null": ["-/-"]},
            {"name": f"{dict_columns['Vacancies'][language]}", "id": "vacancies", "sort_as_null": ["-"]},
            {"name": f"{dict_columns['Distance'][language]}", "id": "distance_km", "sort_as_null": [""]},
            {"name": f"{dict_columns['UpdatedAt'][language]}", "id": "updatedAt"},
        ],
        data=filtered_df.to_dict('records'),
        sort_action='native',
        page_size=APP_TABLE_PAGE_SIZE,
        page_action='native',
        style_table={'overflowX': 'auto', 'width': '100%'},
        style_header={'color': fontColor, 'backgroundColor': backgroundColor, 'textAlign': 'left', 'fontSize': '15px'},
        style_data={'whiteSpace': 'normal', 'textOverflow': 'ellipsis', 'overflow': 'hidden'},
        style_cell={
            'textAlign': 'center',
            'whiteSpace': 'normal',
            'overflow': 'hidden',
            'textOverflow': 'ellipsis',
        },
        style_cell_conditional=[
            {'if': {'column_id': 'link'}, 'width': '25%'},
            {'if': {'column_id': 'address'}, 'width': '25%'},
            {'if': {'column_id': 'capacity_info'}, 'width': '3%'},
            {'if': {'column_id': 'vacancies'}, 'width': '5%'},
            {'if': {'column_id': 'updatedAt'}, 'width': '5%'},
            {'if': {'column_id': 'distance_km'}, 'width': '5%'},
        ],
        style_data_conditional=[
            {'if': {'filter_query': f'{{availability}} = "{dict_columns["AvailabilityStatus"]["Check"]["statusId"]}"'},
                'backgroundColor': dict_columns["AvailabilityStatus"]["Check"]["color"]},
            {'if': {'filter_query': f'{{availability}} = "{dict_columns["AvailabilityStatus"]["Available"]["statusId"]}"'},
                'backgroundColor': dict_columns["AvailabilityStatus"]["Available"]["color"]},
            {'if': {'filter_query': f'{{availability}} = "{dict_columns["AvailabilityStatus"]["Crowded"]["statusId"]}"'},
                'backgroundColor': dict_columns["AvailabilityStatus"]["Crowded"]["color"]},
            {'if': {'filter_query': f'{{availability}} = "{dict_columns["AvailabilityStatus"]["Full"]["statusId"]}"'},
                'backgroundColor': dict_columns["AvailabilityStatus"]["Full"]["color"]},
        ]
    )

    return fig, city_distribution, num_shelters, total_people, verified_shelters, not_verified_shelters, pet_friendly_shelters, shelter_table

if __name__ == '__main__':
    debug_mode = FLASK_ENV == 'production'
    update_shelter_data()  # Run the update function at startup
    logging.info("Starting the server")
    try:
        app.run_server(debug=debug_mode)
    finally:
        logging.info("Shutting down the scheduler")
        scheduler.shutdown()
else:
    logging.info("Starting the server in WSGI mode")
    server = app.server
