import dash
from dash import dcc, html, Input, Output, dash_table, State
import pandas as pd
import plotly.express as px
import json

PAGE_SIZE = 25
COLORS = 1

dict_config = {
    1: {'backgroundColor': 'black', 'fontColor': 'white', 'map_style': 'carto-darkmatter'},
    2: {'backgroundColor': 'white', 'fontColor': 'black', 'map_style': 'carto-positron'}
}

dict_columns = {
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
    'AmountOfShelters': {'pt-br': 'Número de Abrigos', 'en': 'Amount Of Shelters'},
    'AmountOfPeopleSheltered': {'pt-br': 'Número de Pessoas Abrigadas', 'en': 'Amount Of People Sheltered'},
    'SheltersVerified': {'pt-br': 'Verificados', 'en': 'Verified'},
    'SheltersNotVerified': {'pt-br': 'Nāo Verificados', 'en': 'Not Verified'},
    'Search': {'pt-br': 'Buscar por abrigo ou endereço', 'en': 'Search for shelter or address'},
}

dict_columns2 = {
    'availability': 'availability',
    'link': 'link',
}

backgroundColor = dict_config.get(COLORS).get("backgroundColor")
fontColor = dict_config.get(COLORS).get("fontColor")
map_style = dict_config.get(COLORS).get("map_style")

def get_data():
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

    df = df[df['actived'] == True]
    # Add column 'pet_icon' based on 'petFriendly' column
    df['pet_icon'] = df['petFriendly'].apply(lambda x: '🐾' if x else '')
    # Add column 'verification_icon' based on 'verified' column
    df['verification_icon'] = df['verified'].apply(lambda x: '✔️' if x else '❌')

    # Create a new column for capacity information
    df['capacity_info'] = df.apply(lambda row: f"{int(row['shelteredPeople']) if pd.notnull(row['shelteredPeople']) else '-'}/{int(row['capacity']) if pd.notnull(row['capacity']) else '-'}", axis=1)

    # link Column to create hyperlink
    df['link'] = df.apply(create_link, axis=1)

    df['shelter_supplies_str'] = df['shelterSupplies'].apply(lambda x: ', '.join([supply['supply']['name'] for supply in x]))
    df.drop(columns=['shelterSupplies'], inplace=True)

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

    df.drop(['pix','street','neighbourhood','streetNumber','prioritySum','zipCode','createdAt'], axis=1, inplace=True)
    
    df.rename(columns=dict_columns2, inplace=True)
    return df

def data_cities(df):
    cities = df['city'].unique()
    city_options = [{'label': city, 'value': city} for city in cities if city is not None]
    city_options.insert(0, {'label': 'Todas as Cidades', 'value': 'Todas as Cidades'})
    city_options = sorted(city_options, key=lambda x: x['label'])
    return city_options

df = get_formated_data()
city_options = data_cities(df)

app = dash.Dash(__name__)
server = app.server

app.layout = html.Div([
    # Language switcher
    html.Div([
        html.A([
            html.Img(src='https://cdn-icons-png.flaticon.com/128/197/197386.png', style={'cursor': 'pointer', 'margin': '22px', 'width': '25px', 'height': '25px', 'margin-left': '2%'}),
        ], title="brazil icons", id='pt-br', n_clicks=0),  
        html.A([
            html.Img(src='https://cdn-icons-png.flaticon.com/128/197/197484.png', style={'cursor': 'pointer', 'margin': '22px', 'width': '25px', 'height': '25px'}),
        ], title="usa icons", id='en', n_clicks=0),
    ]),
       # Title
    html.H1(id='title', style={'color': fontColor, 'width': '100%',  'margin': '0px', 'textAlign': 'center'}),
    # Search
    html.Div([
        dcc.Input(
            id='search-filter',
            type='text',
            placeholder=f"{dict_columns.get('Search').get('pt-br')}", 
            style={'width': '50%', 'display': 'inline-block', 'padding': '6px', 'margin-right': '2%', 'textAlign': 'center'}
        )
    ], className='dropdown-div', style={'backgroundColor': backgroundColor, 'padding': '10px', 'borderRadius': '5px', 'textAlign': 'center'}),
    # Filters
    html.Div([
        
        html.Div([
            html.Label(id='city-label', style={'color': fontColor}),
            dcc.Dropdown(
                id='city-filter',
                options=city_options,
                value=['Todas as Cidades'],
                multi=True,
                clearable=True,
                style={'color': 'black'}
            )
        ], style={'width': '30%', 'display': 'inline-block', 'margin-right': '1%'}), 
        
        html.Div([
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
        ], style={'width': '30%', 'display': 'inline-block', 'margin-right': '1%'}),
        
        html.Div([
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
        ], style={'width': '13%', 'display': 'inline-block', 'margin-right': '1%'}),
        
        html.Div([
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
        ], style={'width': '13%', 'display': 'inline-block', 'margin-right': '1%'}),
    ], className='dropdown-div', style={'backgroundColor': backgroundColor, 'padding': '5px', 'borderRadius': '5px', 'textAlign': 'center'}),
    # Map, Pie, Table
    html.Div([
        # Map
        html.Div([
            dcc.Graph(id='map'),
        ], style={'width': '40%', 'backgroundColor': backgroundColor, 'display': 'inline-block', 'vertical-align': 'middle', 'margin-right': '2%'}),
        # Pie
        html.Div([
            dcc.Graph(id='city-distribution'),
        ], style={'width': '25%', 'display': 'inline-block', 'vertical-align': 'middle', 'margin-right': '2%'}),
        # Text
        html.Div([
            html.Div(id='num-shelters-div', className='info-div', style={'textAlign': 'center'}),
            html.Div(id='verified-shelters-div', className='info-div', style={'textAlign': 'center'}),
            html.Div(id='pet-friendly-shelters-div', className='info-div', style={'textAlign': 'center'}),
            html.Div(id='total-people-div', className='info-div', style={'textAlign': 'center'}),
        ], style={'width': '25%', 'backgroundColor': backgroundColor, 'display': 'inline-block', 'vertical-align': 'middle', 'margin-right': '2%'}),
    ], className='pie-container', style={'backgroundColor': backgroundColor, 'padding': '10px', 'borderRadius': '5px'}),
    # Table
    html.Div(id='shelter-table-div')
], style={'backgroundColor': backgroundColor})

@app.callback(
    [Output('title', 'children'),
     Output('search-filter', 'placeholder'),
     Output('city-label', 'children'),
     Output('availability-label', 'children'),
     Output('verification-label', 'children'),
     Output('pet-label', 'children'),
     Output('city-filter', 'options')],
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
            dict_columns.get('City').get(language),
            dict_columns.get('Availability').get(language),
            dict_columns.get('VerificationStatus').get(language),
            dict_columns.get('Pet').get(language),
            city_options)

@app.callback(
    [Output('map', 'figure'),
     Output('city-distribution', 'figure'),
     Output('num-shelters-div', 'children'),
     Output('total-people-div', 'children'),
     Output('verified-shelters-div', 'children'),
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
    verified_shelters = html.P(f"{dict_columns.get('SheltersVerified').get(language)}: {len(filtered_df[filtered_df['verified']])} | {dict_columns.get('SheltersNotVerified').get(language)}: {len(filtered_df[~filtered_df['verified']])}", style={'color': fontColor, 'fontWeight': 'bold'})
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
            {
                'if': {
                    'filter_query': '{availability} = "Lotado"',
                },
                'backgroundColor': '#FF4136',
                'color': 'black'
            },
            {
                'if': {
                    'filter_query': '{availability} = "Disponível"',
                },
                'backgroundColor': '#2ECC40',
                'color': 'black'
            },
            {
                'if': {
                    'filter_query': '{availability} = "Cheio"',
                },
                'backgroundColor': '#FF851B',
                'color': 'black'
            },
            {
                'if': {
                    'filter_query': '{availability} = "Consultar"',
                },
                'backgroundColor': '#00BFFF',
                'color': 'black'
            },
        ],
    )

    return fig, city_distribution, num_shelters, total_people, verified_shelters, pet_friendly_shelters, shelter_table

if __name__ == '__main__':
    app.run_server(debug=True)
else:
    server = app.server
