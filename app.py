from flask_sslify import SSLify
import os
import dash
from dash import dcc, html, Input, Output, dash_table, State
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import json
import redis
import subprocess
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify
from datetime import datetime

# Set up Redis connection
redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
client = redis.Redis.from_url(redis_url)

PAGE_SIZE = 25
COLORS = 1

dict_config = {
    1: {'backgroundColor': 'black', 'fontColor': 'white', 'map_style': 'carto-darkmatter'},
    2: {'backgroundColor': 'white', 'fontColor': 'black', 'map_style': 'carto-positron'}
}

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

dict_rename = {
    'availability': 'availability',
    'link': 'link',
}

backgroundColor = dict_config.get(COLORS).get("backgroundColor")
fontColor = dict_config.get(COLORS).get("fontColor")
map_style = dict_config.get(COLORS).get("map_style")

def get_data():
    shelter_data = client.get('shelters')
    if shelter_data:
        return json.loads(shelter_data)
    else:
        with open('shelters.json', 'r') as file:
            return json.load(file)

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
    df['availability'] = df.apply(lambda row: 'Consultar' if pd.isnull(row['capacity']) or pd.isnull(row['shelteredPeople']) 
                                        else ('Lotado' if row['shelteredPeople'] > row['capacity'] 
                                        else ('Cheio' if row['shelteredPeople'] == row['capacity'] 
                                        else 'Disponível')), axis=1)
    # Group cities that have less then 5% to 'Outras'
    city_counts = df['city'].fillna('Desconhecida').value_counts(normalize=True)
    df['city_grouped'] = df['city'].fillna('Desconhecida').apply(lambda x: x if city_counts[x] >= 0.05 else 'Outras Cidades')
    # Drop columns
    df.drop(['pix','street','neighbourhood','streetNumber','prioritySum','zipCode','createdAt'], axis=1, inplace=True)
    # Rename Columns
    df.rename(columns=dict_rename, inplace=True)
    return df

def data_cities(df):
    cities = df['city'].unique()
    city_options = [{'label': city, 'value': city} for city in cities if city is not None]
    city_options.insert(0, {'label': 'Todas as Cidades', 'value': 'Todas as Cidades'})
    city_options = sorted(city_options, key=lambda x: x['label'])
    return city_options

def update_shelter_data():
    try:
        result = subprocess.run(['python', 'get_api_data.py'], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error updating data: {result.stderr}")
        else:
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            client.set('last_update', current_time)
            print("Data updated successfully")
    except Exception as e:
        print(f"Exception during data update: {e}")

def get_last_update_time():
    last_update = client.get('last_update')
    if last_update:
        return last_update.decode('utf-8')
    return 'Never'

df = get_formated_data()
city_options = data_cities(df)

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server

if 'DYNO' in os.environ:  # Only trigger SSLify if on Heroku
    sslify = SSLify(server)

# Schedule the update every 10 minutes
scheduler = BackgroundScheduler()
scheduler.add_job(update_shelter_data, 'interval', minutes=10)
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
    ],
    style={ 'textAlign': 'center'}),
    html.Div(f"Last update: {get_last_update_time()}"),
    #Search
    dbc.Row([
        dbc.Col(dcc.Input(
            id='search-filter',
            type='text',
            placeholder=f"{dict_columns.get('Search').get('pt-br')}", 
            className='responsive-input', 
            style={'textAlign': 'center'}
        ), width=12)
    ], className='dropdown-div', style={'padding': '10px', 'borderRadius': '5px', 'textAlign': 'center'}),
    #Filters
    dbc.Row([
        dbc.Col([
            html.Label(id='city-label', style={'color': fontColor}),
            dcc.Dropdown(
                id='city-filter',
                options=city_options,
                value=['Todas as Cidades'],
                multi=True,
                clearable=True,
                style={'color': 'black'}
            )
        ], xs=12, sm=12, md=6, lg=3, className="mb-3"), 
        dbc.Col([
            html.Label(id='availability-label', style={'color': fontColor}),
            dcc.Dropdown(
                id='availability-filter',
                options=[
                    {'label': 'Todos', 'value': 'Todos'},
                    {'label': 'Disponível', 'value': 'Disponível'},
                    {'label': 'Consultar', 'value': 'Consultar'},
                    {'label': 'Cheio', 'value': 'Cheio'},
                    {'label': 'Lotado', 'value': 'Lotado'},       
                ],
                value=['Disponível', 'Consultar'],
                multi=True,
                clearable=True,
                style={'color': 'black'}
            )
        ], xs=12, sm=12, md=6, lg=3, className="mb-3"),
        dbc.Col([
            html.Label(id='verification-label', style={'color': fontColor}),
            dcc.Dropdown(
                id='verification-filter',
                options=[
                    {'label': 'Sim', 'value': True},
                    {'label': 'Não', 'value': False},
                    {'label': 'Todos', 'value': 'Todos'}
                ],
                value='Todos',
                clearable=False,
                style={'color': 'black'}
            )
        ], xs=12, sm=12, md=6, lg=3, className="mb-3"),
        dbc.Col([
            html.Label(id='pet-label', style={'color': fontColor}),
            dcc.Dropdown(
                id='pet-filter',
                options=[
                    {'label': 'Sim', 'value': True},
                    {'label': 'Não', 'value': False},
                    {'label': 'Todos', 'value': 'Todos'}
                ],
                value='Todos',
                clearable=False,
                style={'color': 'black'}
            )
        ], xs=12, sm=12, md=6, lg=3, className="mb-3"),
    ], style={'backgroundColor': backgroundColor, 'padding': '10px', 'borderRadius': '5px'}
    ),
    #Graphs
    dbc.Row([
       dbc.Col([
            dbc.Button(id="hide-info", className="mb-2"),
            dbc.Row(dbc.Col(id='num-shelters-div')),
            dbc.Row(dbc.Col(id='verified-shelters-div')),
            dbc.Row(dbc.Col(id='not-verified-shelters-div')),
            dbc.Row(dbc.Col(id='pet-friendly-shelters-div')),
            dbc.Row(dbc.Col(id='total-people-div')),
        ], xs=12, sm=12, md=6, lg=3, className="mb-3"
        #className="d-flex flex-column align-items-center justify-content-center"
        ),
        dbc.Col([
            dbc.Button(id="hide-map", className="mb-2"),
            dcc.Graph(id='map', style={'display': 'block'})
        ], xs=12, sm=12, md=6, lg=6, className="mb-3"),
        dbc.Col([
            dbc.Button(id="hide-city-distribution", className="mb-2"),
            dcc.Graph(id='city-distribution', style={'display': 'block'})
        ], xs=12, sm=12, md=6, lg=3, className="mb-3"),
        ], 
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
     Output('availability-label', 'children'),
     Output('verification-label', 'children'),
     Output('pet-label', 'children'),
     Output('city-filter', 'options'),
     Output('hide-info', 'children'),
     Output('hide-map', 'children'),
     Output('hide-city-distribution', 'children')],
    [Input('pt-br', 'n_clicks'),
     Input('en', 'n_clicks')],
    [State('search-filter', 'placeholder'),
     State('city-label', 'children'),
     State('availability-label', 'children'),
     State('verification-label', 'children'),
     State('pet-label', 'children')]
)
def update_language(pt_clicks, en_clicks, search_placeholder, city_label, availability_label, verification_label, pet_label):
    language = 'pt-br'
    if en_clicks and (not pt_clicks or en_clicks > pt_clicks):
        language = 'en'
    
    city_options = data_cities(df)
    
    return (f"{dict_columns.get('Shelter').get(language)}s - Rio Grande do Sul",
            dict_columns.get('Search').get(language),
            dict_columns.get('City').get(language)+':',
            dict_columns.get('Availability').get(language)+':',
            dict_columns.get('VerificationStatus').get(language)+':',
            dict_columns.get('Pet').get(language)+':',
            city_options,
            dict_columns.get('Hide').get(language),
            dict_columns.get('Hide').get(language),
            dict_columns.get('Hide').get(language))

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
     Input('en', 'n_clicks')]
)
def update_data(search, city, verification, pet, availability, pt_clicks, en_clicks):
    language = 'pt-br'
    if en_clicks and (not pt_clicks or en_clicks > pt_clicks):
        language = 'en'

    filtered_df = get_formated_data()
    
    if search:
        search = search.lower()
        filtered_df = filtered_df[
            filtered_df.apply(
                lambda row: row.astype(str).str.lower().str.contains(search).any(), axis=1
            )
        ]

    if 'Todas as Cidades' not in city and len(city) > 0:
        filtered_df = filtered_df[filtered_df['city'].isin(city)]
    
    if pet != 'Todos':
        filtered_df = filtered_df[filtered_df['petFriendly'] == pet]
    
    if verification != 'Todos':
        filtered_df = filtered_df[filtered_df['verified'] == verification]

    if 'Todos' not in availability and len(availability) > 0:
        filtered_df = filtered_df[filtered_df['availability'].isin(availability)]

    #Pie Graph
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
    #Map Graph
    fig = px.scatter_mapbox(
        filtered_df,
        lat="latitude",
        lon="longitude",
        hover_name="name",
        hover_data=["city", "capacity", "shelteredPeople"],
        color="availability",
        color_discrete_map={
            'Lotado': 'red',
            'Disponível': 'green',
            'Cheio': 'orange',
            'Consultar': 'blue'
        },
        zoom=9,
    )

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
            {'if': {'filter_query': '{availability} = "Lotado"',},'backgroundColor': '#FF4136'},
            {'if': {'filter_query': '{availability} = "Disponível"',},'backgroundColor': '#2ECC40'},
            {'if': {'filter_query': '{availability} = "Cheio"',},'backgroundColor': '#FF851B'},
            {'if': {'filter_query': '{availability} = "Consultar"',},'backgroundColor': '#00BFFF'},
        ],
    )

    return fig, city_distribution, num_shelters, total_people, verified_shelters, not_verified_shelters, pet_friendly_shelters, shelter_table

if __name__ == '__main__':
    debug_mode = os.getenv('FLASK_ENV') != 'production'
    try:
        app.run_server(debug=debug_mode)
    finally:
        scheduler.shutdown()
else:
    server = app.server

