import os
import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import json
import redis
import subprocess
import requests
import pytz
from flask_sslify import SSLify
from dash import dcc, html, Input, Output, dash_table, State
from apscheduler.schedulers.background import BackgroundScheduler
from flask import jsonify, session, request
from datetime import datetime
from utils import generate_secret_key

# Set up Redis connection
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
client = redis.Redis.from_url(redis_url)

COLORS = 1
SECRET_KEY = generate_secret_key()
PAGE_SIZE = 25
CALL_API_MINUTES = 60
DEFAULT_LANGUAGE = 'pt-br'

dict_config = {
    1: {'backgroundColor': '#0E0F0E', 'fontColor': 'white', 'map_style': 'carto-darkmatter'},
    2: {'backgroundColor': 'white', 'fontColor': 'black', 'map_style': 'carto-positron'}
}

backgroundColor = dict_config.get(COLORS).get("backgroundColor")
fontColor = dict_config.get(COLORS).get("fontColor")
map_style = dict_config.get(COLORS).get("map_style")

dict_columns = {
    'Hide': {'pt-br': 'Esconder', 'en': 'Hide'},
    'Yes': {'pt-br': 'Sim', 'en': 'Yes'},
    'No': {'pt-br': 'Não', 'en': 'No'},
    'All': {'pt-br': 'Todos', 'en': 'All'},
    'Pet': {'pt-br': 'Animais', 'en': 'Pet'},
    'AllCities': {'pt-br': 'Todas', 'en': 'All'},
    'City': {'pt-br': 'Cidade', 'en': 'City'},
    'Shelter': {'pt-br': 'Abrigo', 'en': 'Shelter'},
    'People': {'pt-br': 'Pessoas', 'en': 'People'},
    'UpdatedAt': {'pt-br': 'Atualizado', 'en': 'Updated At'},
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
}

dict_availabilityStatus = {
    'AvailabilityStatus': {
        'Available' : {'statusId': 1, 'pt-br': 'Disponível', 'en': 'Available', 'color':'#2ECC40'},
        'Check' : {'statusId': 2, 'pt-br': 'Consultar', 'en': 'Check', 'color':'#00BFFF'},
        'Crowded' : {'statusId': 3, 'pt-br': 'Cheio', 'en': 'Crowded', 'color':'#FFB347'},
        'Full' : {'statusId': 4, 'pt-br': 'Lotado', 'en': 'Full', 'color':'#FF6347'},
        'Location' : {'statusId': 5, 'pt-br': 'Sua Localização', 'en': 'Your Location', 'color': fontColor},
        }
}

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

def format_date(data_original):
    data_datetime = pd.to_datetime(data_original)
    return data_datetime.strftime("%d/%m/%Y %H:%M:%S")

def map_availability(row, key):
    if pd.isnull(row['capacity']) or pd.isnull(row['shelteredPeople']):
        status = 'Check'
    elif row['shelteredPeople'] > row['capacity']:
        status = 'Full'
    elif row['shelteredPeople'] == row['capacity']:
        status = 'Crowded'
    else:
        status = 'Available'
    
    return dict_availabilityStatus['AvailabilityStatus'][status][key]

def create_link(row):
    icons = f"{row['pet_icon']}"
    return f"{icons} [{row['name']}](https://sos-rs.com/abrigo/{row['id']})"

def format_date(data_original):
    data_datetime = pd.to_datetime(data_original)
    return data_datetime.strftime("%d/%m/%Y %H:%M:%S")

def get_formated_data():
    df = pd.json_normalize(get_data())
    # Filter actived shelters
    df = df[df['actived'] == True]
    # Add column 'pet_icon' based on 'petFriendly' column
    df['pet_icon'] = df['petFriendly'].apply(lambda x: '🐾' if x else '')
    # Add column 'verification_icon' based on 'verified' column
    df['verification_icon'] = df['verified'].apply(lambda x: '✔️' if x else '❌')
    # Create a new column for capacity information
    df['capacity_info'] = df.apply(lambda row: f"{int(row['shelteredPeople']) if pd.notnull(row['shelteredPeople']) else '-'}/{int(row['capacity']) if pd.notnull(row['capacity']) else '-'}", axis=1)
    # link Column to create hyperlink
    df['link'] = df.apply(create_link, axis=1)
    # Convert shelter_supplies to str
    df['shelter_supplies_str'] = df['shelterSupplies'].apply(lambda x: ', '.join([supply['supply']['name'] for supply in x]))
    df.drop(columns=['shelterSupplies'], inplace=True)
    # Clean duplicated Shelters
    df.drop_duplicates(inplace=True)
    # Format Date
    df['updatedAt'] = df['updatedAt'].apply(format_date)
    # Order by 'updatedAt' DESC
    df = df.sort_values(by='updatedAt', ascending=False)
    # Add availability
    # df['availability'] = df.apply(lambda row: 'Consultar' if pd.isnull(row['capacity']) or pd.isnull(row['shelteredPeople']) 
    #                                     else ('Lotado' if row['shelteredPeople'] > row['capacity'] 
    #                                     else ('Cheio' if row['shelteredPeople'] == row['capacity'] 
    #                                     else 'Disponível')), axis=1)

    df['availability'] = df.apply(lambda row: map_availability(row, 'statusId'), axis=1)

        # Aplicar a função ao DataFrame
    #df['availability_id'] = df.apply(lambda row: map_availability(row, language), axis=1)
    #df['availability_en'] = df.apply(lambda row: map_availability(row, 'en'), axis=1)
    
    # Group cities that have less then 5% to 'Outras'
    city_counts = df['city'].fillna('Desconhecida').value_counts(normalize=True)
    df['city_grouped'] = df['city'].fillna('Desconhecida').apply(lambda x: x if city_counts[x] >= 0.05 else 'Outras Cidades')
    # Drop columns
    df.drop(['pix','street','neighbourhood','streetNumber','prioritySum','zipCode','createdAt'], axis=1, inplace=True)
    # Rename Columns
    df.rename(columns=dict_rename, inplace=True)
    return df

def data_cities(df, language):
    df['city'] = df['city'].fillna('').astype(str)
    cities = df['city'].unique()
    city_options = [{'label': city, 'value': city} for city in cities if city is not None]
    city_options.insert(0, {'label': dict_columns['AllCities'][language], 'value': dict_columns['AllCities'][language]})
    city_options = sorted(city_options, key=lambda x: x['label'])
    return city_options

def update_shelter_data():
    try:
        result = subprocess.run(['python', 'get_api_data.py'], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error updating data: {result.stderr}")
        else:
            current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            client.set('last_update', current_time)
            print("Data updated successfully")
    except Exception as e:
        print(f"Exception during data update: {e}")

def get_last_update_time():
    last_update = client.get('last_update')
    if last_update:
        return last_update.decode('utf-8')
    return ''

def get_last_update_time():
    last_update = client.get('last_update')
    if last_update:
        last_update_utc = datetime.strptime(last_update.decode('utf-8'), '%Y-%m-%d %H:%M:%S')
        timezone = session.get('timezone', 'UTC')
        local_tz = pytz.timezone(timezone)
        last_update_local = last_update_utc.replace(tzinfo=pytz.utc).astimezone(local_tz)
        return last_update_local.strftime('%Y-%m-%d %H:%M:%S')
    return ''

def get_user_language_and_location(): #TODO: fix this function
    try:
        if os.getenv('FLASK_ENV') == 'production':
            ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0]
            response = requests.get(f'https://ipinfo.io/{ip}/json').json()
        else:
            ip = "193.19.205.186"
            response = {'ip': '193.19.205.186', 'city': 'São Paulo', 'region': 'São Paulo', 'country': 'BR', 'loc': '-23.5475,-46.6361', 'org': 'AS203020 HostRoyale Technologies Pvt Ltd', 'postal': '01000-000', 'timezone': 'America/Sao_Paulo', 'readme': 'https://ipinfo.io/missingauth'}
        loc = response.get('loc')
        country = response.get('country')
        city = response.get('city')
        timezone = response.get('timezone')
        print(f"{response}")
        if loc:
            lat, lon = loc.split(',')
            return ('pt-br' if country == 'BR' else 'en', float(lat), float(lon), city, timezone)
    except Exception as e:
        print(f"Error determining user location: {e}")
    if os.getenv('FLASK_ENV') == 'production':
        return DEFAULT_LANGUAGE, None, None, '', 'America/Sao_Paulo'
    else:
        return 'en', -30.0290596, -51.2345029, "Perth", "Australia/Perth" #values for test in DEV

df = get_formated_data()

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True)
server = app.server
app.server.config['SECRET_KEY'] = SECRET_KEY

if 'DYNO' in os.environ:  # Only trigger SSLify if on Heroku
    sslify = SSLify(server)

@server.before_request
def before_request():
    if 'language' not in session or 'lat' not in session or 'lon' not in session:
        user_language, lat, lon, city, timezone = get_user_language_and_location()
        current_timestamp = datetime.utcnow()
        session['language'] = user_language
        session['lat'] = lat
        session['lon'] = lon
        session['city'] = city
        session['timezone'] = timezone
        print(f"Session values ({current_timestamp}): {session['language'] = }, {session['lat'] = }, {session['lon'] = }, {session['city'] = }, {session['timezone'] = }")

# Scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(update_shelter_data, 'interval', minutes=CALL_API_MINUTES)
scheduler.start()

@server.route('/update-data', methods=['GET'])
def update_data():
    try:
        update_shelter_data()
        return jsonify({"message": "Data update triggered"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

app.layout = dbc.Container([
    #Language
    dbc.Row([
        dbc.Col(html.Div([
            html.A([
                html.Img(src='https://cdn-icons-png.flaticon.com/128/197/197386.png', style={'cursor': 'pointer', 'width': '25px', 'height': '25px', 'margin-right': '7px'}),
            ], title="brazil icons", id='pt-br', n_clicks=0),
            html.A([
                html.Img(src='https://cdn-icons-png.flaticon.com/128/197/197484.png', style={'cursor': 'pointer', 'width': '25px', 'height': '25px', 'margin-left': '7px'}),
            ], title="usa icons", id='en', n_clicks=0),
        ]), width="auto"),
    ], className="justify-content-center",
    style={'padding': '10px'}),
    #Title
    dbc.Row([
        dbc.Col(html.H1(id='title', style={'color': fontColor, 'textAlign': 'center'}), width=12)
    ], style={'textAlign': 'center', 'margin-bottom': '5px'}),
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
    ], style={'textAlign': 'center', 'margin-bottom': '5px'}),
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
    ], style={'backgroundColor': backgroundColor, 'margin-bottom': '5px'}
    ),
    #Graphs
    dbc.Row([
       dbc.Col([
            dbc.Button(id="hide-info"),
            dbc.Row(dbc.Col(id='num-shelters-div'), style={'margin-top': '5px'}),
            dbc.Row(dbc.Col(id='verified-shelters-div')),
            dbc.Row(dbc.Col(id='not-verified-shelters-div')),
            dbc.Row(dbc.Col(id='pet-friendly-shelters-div')),
            dbc.Row(dbc.Col(id='total-people-div')),
        ], xs=12, sm=12, md=6, lg=3, className="mb-3"
        ),
        dbc.Col([
            dbc.Button(id="hide-map"),
            dcc.Graph(id='map', style={'display': 'block'})
        ], xs=12, sm=12, md=6, lg=6, className="mb-3", style={'margin-bottom': '10px'}),
        dbc.Col([
            dbc.Button(id="hide-city-distribution"),
            dcc.Graph(id='city-distribution', style={'display': 'block'})
        ], xs=12, sm=12, md=6, lg=3, className="mb-3"),
        ], style={'backgroundColor': backgroundColor, 'textAlign': 'center', 'margin-bottom': '5px'} 
    ),
    #Table
    dbc.Row([
        dbc.Col(html.Div(id='shelter-table-div'), width=12)
    ])

], fluid=True
, style={'backgroundColor': backgroundColor}
)

@app.callback(
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
    
    return new_style, new_style, new_style, new_style, new_style

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
def update_language(pt_clicks, en_clicks, search_placeholder, city_label, city_options, city_values, availability_label, availability_options, availability_values,  verification_label, verification_options, verification_values, pet_label, pet_options, pet_values):
    language = session.get('language', 'en')
    if en_clicks and (not pt_clicks or en_clicks > pt_clicks):
        language = 'en'
    elif pt_clicks and (not en_clicks or pt_clicks > en_clicks):
        language = 'pt-br'
    
    city_options = data_cities(df,language)
    last_update_time = f"{dict_columns['UpdatedAt'][language]}: {get_last_update_time()}"

    availability_options = [
        {'label': dict_columns.get('All').get(language), 'value': dict_columns.get('All').get(language)},
        {'label': dict_availabilityStatus['AvailabilityStatus']['Available'][language], 'value': dict_availabilityStatus['AvailabilityStatus']['Available']['statusId']},
        {'label': dict_availabilityStatus['AvailabilityStatus']['Check'][language], 'value': dict_availabilityStatus['AvailabilityStatus']['Check']['statusId']},
        {'label': dict_availabilityStatus['AvailabilityStatus']['Crowded'][language], 'value': dict_availabilityStatus['AvailabilityStatus']['Crowded']['statusId']},
        {'label': dict_availabilityStatus['AvailabilityStatus']['Full'][language], 'value': dict_availabilityStatus['AvailabilityStatus']['Full']['statusId']},
    ]
    
    availability_values = [
        dict_availabilityStatus['AvailabilityStatus']['Available']['statusId'],
        dict_availabilityStatus['AvailabilityStatus']['Check']['statusId']
    ]

    simple_options = [
        {'label': dict_columns.get('Yes').get(language), 'value': True},
        {'label': dict_columns.get('No').get(language), 'value': False},
        {'label': dict_columns.get('All').get(language), 'value': dict_columns['All'][language]}
    ]
    
    verification_options = simple_options

    pet_options = simple_options

    simple_values = dict_columns['All'][language]

    verification_values = simple_values

    pet_values = simple_values

    city_values = dict_columns['AllCities'][language]
    
    return (f"{dict_columns.get('Shelter').get(language)}s - Rio Grande do Sul",
            dict_columns.get('Search').get(language),
            dict_columns.get('City').get(language)+':',
            city_options,
            city_values,
            dict_columns.get('Availability').get(language)+':',
            availability_options,
            availability_values,
            dict_columns.get('VerificationStatus').get(language)+':',
            verification_options,
            verification_values,
            dict_columns.get('Pet').get(language)+':',
            pet_options,
            pet_values,
            dict_columns.get('Hide').get(language),
            dict_columns.get('Hide').get(language),
            dict_columns.get('Hide').get(language),
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
    language = session.get('language', 'en')
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


    # Pie Graph
    city_distribution = px.pie(
        filtered_df,
        names='city_grouped',
        hole=0.25,
        color_discrete_sequence=px.colors.qualitative.Plotly
    )
    city_distribution.update_layout(
        title_font_color=fontColor,
        font_color=fontColor,
        paper_bgcolor=backgroundColor,
        plot_bgcolor=fontColor,
    )
    
    # Map Graph
    lat = session.get('lat')
    lon = session.get('lon')
    city = session.get('city')

    new_point = pd.DataFrame({
    'latitude': [lat],
    'longitude': [lon],
    'name': dict_availabilityStatus['AvailabilityStatus']['Location'][language],
    'city': city,
    'capacity': '',
    'shelteredPeople': '',
    'availabilityDescription': dict_availabilityStatus['AvailabilityStatus']['Location'][language]
    })

    labels = {
        'latitude': 'Latitude',
        'longitude': 'Longitude',
        'name': dict_columns.get('Shelter').get(language),
        'city': dict_columns.get('City').get(language),
        'capacity': dict_columns.get('Capacity').get(language),
        'shelteredPeople': dict_columns.get('AmountOfPeopleSheltered').get(language),
        'availabilityDescription': dict_columns.get('Availability').get(language)
    }

    filtered_df['availabilityDescription'] = filtered_df.apply(lambda row: map_availability(row, language), axis=1)

    updated_data = pd.concat([filtered_df, new_point], ignore_index=True)

    updated_data[['city', 'capacity', 'shelteredPeople', 'availabilityDescription']] = updated_data[['city', 'capacity', 'shelteredPeople', 'availabilityDescription']].fillna("")

    fig = px.scatter_mapbox(
        updated_data,
        lat="latitude",
        lon="longitude",
        hover_name="name",
        #hover_data={'customdata': False},  # Desabilita hover_data padrão para customdata
        hover_data={'city': True, 'capacity': True, 'shelteredPeople': True, 'availabilityDescription': True},
        #custom_data=['city', 'capacity', 'shelteredPeople', 'availability_en'],
        color="availabilityDescription",
        color_discrete_map={
            dict_availabilityStatus['AvailabilityStatus']['Available'][language]: dict_availabilityStatus['AvailabilityStatus']['Available']['color'],
            dict_availabilityStatus['AvailabilityStatus']['Check'][language]: dict_availabilityStatus['AvailabilityStatus']['Check']['color'],
            dict_availabilityStatus['AvailabilityStatus']['Crowded'][language] : dict_availabilityStatus['AvailabilityStatus']['Crowded']['color'],
            dict_availabilityStatus['AvailabilityStatus']['Full'][language]: dict_availabilityStatus['AvailabilityStatus']['Full']['color'],
            dict_availabilityStatus['AvailabilityStatus']['Location'][language]: dict_availabilityStatus['AvailabilityStatus']['Location']['color']
        },
        labels=labels,
        zoom=9,
    )

    fig.update_traces(marker=dict(size=12))  # PIN size

    # # Atualizar layout para exibir customdata corretamente
    # fig.update_traces(
    #     hovertemplate="<br>".join([
    #         "Nome: %{hovertext}",
    #         "Cidade: %{customdata[0]}",
    #         "Capacidade: %{customdata[1]}",
    #         "Pessoas Alojadas: %{customdata[2]}",
    #         "Disponibilidade (EN): %{customdata[3]}"
    #     ])
    # )

    fig.update_layout(mapbox_style=map_style)
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor=backgroundColor)
    fig.update_layout( 
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
    
    num_shelters = html.P(f"{dict_columns.get('AmountOfShelters').get(language)}: {len(filtered_df)}", style={'color': fontColor, 'fontWeight': 'bold'})
    total_people = html.P(f"{dict_columns.get('AmountOfPeopleSheltered').get(language)}: {int(filtered_df['shelteredPeople'].sum())}", style={'color': fontColor, 'fontWeight': 'bold'})
    verified_shelters = html.P(f"{dict_columns.get('SheltersVerified').get(language)}: {len(filtered_df[filtered_df['verified']])}", style={'color': fontColor, 'fontWeight': 'bold'})
    not_verified_shelters = html.P(f"{dict_columns.get('SheltersNotVerified').get(language)}: {len(filtered_df[~filtered_df['verified']])}", style={'color': fontColor, 'fontWeight': 'bold'})
    pet_friendly_shelters = html.P(f"{dict_columns.get('PetFriendly').get(language)}: {filtered_df['petFriendly'].sum()}", style={'color': fontColor, 'fontWeight': 'bold'})

    shelter_table = dash_table.DataTable(
        columns=[
            {"name": f"{dict_columns.get('Shelter').get(language)}", "id": "link", "presentation": "markdown"},
            {"name": f"{dict_columns.get('Address').get(language)}", "id": "address"},
            {"name": f"{dict_columns.get('City').get(language)}", "id": "city"},
            {"name": f"{dict_columns.get('Capacity').get(language)}", "id": "capacity_info"},
            {"name": f"{dict_columns.get('UpdatedAt').get(language)}", "id": "updatedAt"},
        ],
        data=filtered_df.to_dict('records'),
        sort_action='native',
        page_size=PAGE_SIZE,
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
            {'if': {'column_id': 'city'}, 'width': '5%'},
            {'if': {'column_id': 'capacity_info'}, 'width': '5%'},
            {'if': {'column_id': 'updatedAt'}, 'width': '5%'}, 
        ],
        style_data_conditional=[
            {'if': {'filter_query': f'{{availability}} = "{dict_availabilityStatus["AvailabilityStatus"]["Check"]["statusId"]}"'},
                'backgroundColor': dict_availabilityStatus["AvailabilityStatus"]["Check"]["color"]},
            {'if': {'filter_query': f'{{availability}} = "{dict_availabilityStatus["AvailabilityStatus"]["Available"]["statusId"]}"'},
                'backgroundColor': dict_availabilityStatus["AvailabilityStatus"]["Available"]["color"]},
            {'if': {'filter_query': f'{{availability}} = "{dict_availabilityStatus["AvailabilityStatus"]["Crowded"]["statusId"]}"'},
                'backgroundColor': dict_availabilityStatus["AvailabilityStatus"]["Crowded"]["color"]},
            {'if': {'filter_query': f'{{availability}} = "{dict_availabilityStatus["AvailabilityStatus"]["Full"]["statusId"]}"'},
                'backgroundColor': dict_availabilityStatus["AvailabilityStatus"]["Full"]["color"]},
    ]

    )

    return fig, city_distribution, num_shelters, total_people, verified_shelters, not_verified_shelters, pet_friendly_shelters, shelter_table

if __name__ == '__main__':
    debug_mode = os.getenv('FLASK_ENV') != 'production'
    update_shelter_data()  # Run the update function at startup
    try:
        app.run_server(debug=debug_mode)
    finally:
        scheduler.shutdown()
else:
    server = app.server
