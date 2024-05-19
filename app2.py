import dash
from dash import dcc, html, Input, Output, dash_table
import pandas as pd
import plotly.express as px
import json

get_config = 1
language = "pt-br"
dict_config = {
    1: {'backgroundColor' : 'black','fontColor' : 'white','map_style' : 'carto-darkmatter'},
    2: {'backgroundColor' : 'white','fontColor' : 'black','map_style' : 'carto-positron'}
}

dict_columns = {
    'Yes': {'pt-br':'Sim', 'en':'Yes'},
    'No': {'pt-br':'Não', 'en':'No'},
    'All': {'pt-br':'Todos', 'en':'All'},
    'AllCities': {'pt-br':'Todas', 'en':'All'},
    'City': {'pt-br':'Cidade', 'en':'City'},
    'Shelter': {'pt-br':'Abrigo', 'en':'Shelter'},
    'People': {'pt-br':'Pessoas', 'en':'People'},
    'UpdatedAt': {'pt-br':'Atualizado', 'en':'Updated At'},
    'Address': {'pt-br':'Endereço', 'en':'Address'},
    'Capacity': {'pt-br':'Capacidade', 'en':'Capacity'},
    'Availability': {'pt-br':'Disponibilidade', 'en':'Availability'},
    'VerificationStatus': {'pt-br':'Status de Verificação', 'en':'Verification Status'},
    'PetFriendly': {'pt-br':'Pet Friendly', 'en':'Pet Friendly'},
    'AmountOfShelters': {'pt-br':'Número de Abrigos', 'en':'Amount Of Shelters'},
    'AmountOfPeopleSheltered': {'pt-br':'Número de Pessoas Abrigadas', 'en':'Amount Of People Sheltered'},
    'SheltersVerified': {'pt-br':'Verificados', 'en':'Verified'},
    'SheltersNotVerified': {'pt-br':'Nāo Verificados', 'en':'Not Verified'},
    'Search': {'pt-br':'Buscar por abrigo ou endereço', 'en':'Search for shelter or address'},
    } 

dict_columns2 = {
    'availability':'availability',
    'link':'link',  
    } 
    
backgroundColor = dict_config.get(get_config).get("backgroundColor")
fontColor = dict_config.get(get_config).get("fontColor")
map_style = dict_config.get(get_config).get("map_style")

def get_data():
    with open('shelters.json', 'r') as file:
        return json.load(file)

def create_link(row):
    return f"[{row['name']}](https://sos-rs.com/abrigo/{row['id']})"

def format_date(data_original):
    data_datetime = pd.to_datetime(data_original)
    return data_datetime.strftime("%d/%m/%Y %H:%M:%S")

def get_formated_data():
    df = pd.json_normalize(get_data())
    df['link'] = df.apply(create_link, axis=1)
    df['verified_status'] = df['verified'].apply(lambda x: 'Verificado' if x else 'Não Verificado')
    df['shelter_supplies_str'] = df['shelterSupplies'].apply(lambda x: ', '.join([supply['supply']['name'] for supply in x]))
    df.drop(columns=['shelterSupplies'], inplace=True)
    df.drop_duplicates(inplace=True)
    df['updatedAt'] = df['updatedAt'].apply(format_date)
    df = df.sort_values(by='updatedAt', ascending=False)
    df['availability'] = df.apply(lambda row: 'Consultar' if pd.isnull(row['capacity']) or pd.isnull(row['shelteredPeople']) 
                                  else ('Lotado' if row['shelteredPeople'] > row['capacity'] 
                                  else ('Cheio' if row['shelteredPeople'] == row['capacity'] 
                                  else 'Disponível')), axis=1)
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

app.layout = html.Div([
    html.H1(f"{dict_columns.get('Shelter').get(language)}s - Rio Grande do Sul", style={'color': fontColor, 'textAlign': 'center'}),
    html.Div([
        dcc.Input(id='search-filter', type='text', placeholder=f"{dict_columns.get('Search').get(language)}", style={'width': '30%', 'padding': '6px', 'textAlign': 'center'})
    ], style={'backgroundColor': backgroundColor, 'padding': '10px', 'borderRadius': '5px', 'textAlign': 'center'}),
    html.Div([
        html.Div([
            html.Label(f"{dict_columns.get('City').get(language)}:", style={'color': fontColor}),
            dcc.Dropdown(id='city-filter', options=city_options, value=['Todas as Cidades'], multi=True, clearable=True, style={'color': 'black'})
        ], style={'width': '20%', 'display': 'inline-block', 'margin-right': '2%'}),
        html.Div([
            html.Label(f"{dict_columns.get('Availability').get(language)}:", style={'color': fontColor}),
            dcc.Dropdown(id='availability-filter', options=[
                {'label': 'Todos', 'value': 'Todos'},
                {'label': 'Disponível', 'value': 'Disponível'},
                {'label': 'Consultar', 'value': 'Consultar'},
                {'label': 'Cheio', 'value': 'Cheio'},
                {'label': 'Lotado', 'value': 'Lotado'}
            ], value=['Disponível','Consultar'], multi=True, clearable=True, style={'color': 'black'})
        ], style={'width': '20%', 'display': 'inline-block', 'margin-right': '2%'}),
        html.Div([
            html.Label(f"{dict_columns.get('VerificationStatus').get(language)}:", style={'color': fontColor}),
            dcc.Dropdown(id='verification-filter', options=[
                {'label': 'Verificado', 'value': 'Verificado'},
                {'label': 'Não Verificado', 'value': 'Não Verificado'},
                {'label': 'Todos', 'value': 'Todos'}
            ], value='Todos', clearable=False, style={'color': 'black'})
        ], style={'width': '20%', 'display': 'inline-block', 'margin-right': '2%'}),
        html.Div([
            html.Label(f"{dict_columns.get('PetFriendly').get(language)}:", style={'color': fontColor}),
            dcc.Dropdown(id='pet-filter', options=[
                {'label': 'Sim', 'value': True},
                {'label': 'Não', 'value': False},
                {'label': 'Todos', 'value': 'Todos'}
            ], value='Todos', clearable=False, style={'color': 'black'})
        ], style={'width': '20%', 'display': 'inline-block', 'margin-right': '2%'}),
    ], style={'backgroundColor': backgroundColor, 'padding': '10px', 'borderRadius': '5px', 'textAlign': 'center'}),
    html.Div([
        html.Div([dcc.Graph(id='map')], style={'width': '40%', 'display': 'inline-block', 'vertical-align': 'middle', 'margin-right': '2%'}),
        html.Div([dcc.Graph(id='city-distribution')], style={'width': '25%', 'display': 'inline-block', 'vertical-align': 'middle', 'margin-right': '2%'}),
        html.Div([dcc.Graph(id='availability-distribution')], style={'width': '25%', 'display': 'inline-block', 'vertical-align': 'middle'})
    ]),
    dash_table.DataTable(
        id='shelters-table',
        columns=[{"name": col, "id": col, 'presentation': 'markdown'} if col == 'Abrigo' else {"name": col, "id": col} for col in df.columns],
        data=df.to_dict('records'),
        filter_action="native",
        sort_action="native",
        sort_mode="multi",
        page_action="native",
        page_current=0,
        page_size=10,
        style_header={'backgroundColor': 'rgb(30, 30, 30)', 'color': 'white', 'textAlign': 'center'},
        style_data={'backgroundColor': 'rgb(50, 50, 50)', 'color': 'white', 'textAlign': 'center'},
        style_data_conditional=[
            {
                'if': {'row_index': 'odd'},
                'backgroundColor': 'rgb(60, 60, 60)'
            }
        ],
        style_cell={'padding': '5px'}
    )
], style={'backgroundColor': backgroundColor, 'fontColor': fontColor})

@app.callback(
    Output('shelters-table', 'data'),
    Input('search-filter', 'value'),
    Input('city-filter', 'value'),
    Input('availability-filter', 'value'),
    Input('verification-filter', 'value'),
    Input('pet-filter', 'value')
)
def update_table(search_filter, city_filter, availability_filter, verification_filter, pet_filter):
    dff = df.copy()
    if search_filter:
        dff = dff[dff.apply(lambda row: row.astype(str).str.contains(search_filter, case=False).any(), axis=1)]
    if 'Todas as Cidades' not in city_filter:
        dff = dff[dff['city'].isin(city_filter)]
    if 'Todos' not in availability_filter:
        dff = dff[dff['availability'].isin(availability_filter)]
    if verification_filter != 'Todos':
        dff = dff[dff['verified_status'] == verification_filter]
    if pet_filter != 'Todos':
        dff = dff[dff['petFriendly'] == pet_filter]
    return dff.to_dict('records')

@app.callback(
    Output('map', 'figure'),
    Input('search-filter', 'value'),
    Input('city-filter', 'value'),
    Input('availability-filter', 'value'),
    Input('verification-filter', 'value'),
    Input('pet-filter', 'value')
)
def update_map(search_filter, city_filter, availability_filter, verification_filter, pet_filter):
    dff = df.copy()
    if search_filter:
        dff = dff[dff.apply(lambda row: row.astype(str).str.contains(search_filter, case=False).any(), axis=1)]
    if 'Todas as Cidades' not in city_filter:
        dff = dff[dff['city'].isin(city_filter)]
    if 'Todos' not in availability_filter:
        dff = dff[dff['availability'].isin(availability_filter)]
    if verification_filter != 'Todos':
        dff = dff[dff['verified_status'] == verification_filter]
    if pet_filter != 'Todos':
        dff = dff[dff['petFriendly'] == pet_filter]
    fig = px.scatter_mapbox(dff, lat="latitude", lon="longitude", color="availability", size_max=15, zoom=6,
                            hover_data={"name": True, "city": True, "availability": True, "link": True})
    fig.update_layout(mapbox_style=map_style)
    return fig

@app.callback(
    Output('city-distribution', 'figure'),
    Input('search-filter', 'value'),
    Input('city-filter', 'value'),
    Input('availability-filter', 'value'),
    Input('verification-filter', 'value'),
    Input('pet-filter', 'value')
)
def update_city_distribution(search_filter, city_filter, availability_filter, verification_filter, pet_filter):
    dff = df.copy()
    if search_filter:
        dff = dff[dff.apply(lambda row: row.astype(str).str.contains(search_filter, case=False).any(), axis=1)]
    if 'Todas as Cidades' not in city_filter:
        dff = dff[dff['city'].isin(city_filter)]
    if 'Todos' not in availability_filter:
        dff = dff[dff['availability'].isin(availability_filter)]
    if verification_filter != 'Todos':
        dff = dff[dff['verified_status'] == verification_filter]
    if pet_filter != 'Todos':
        dff = dff[dff['petFriendly'] == pet_filter]
    city_counts = dff['city'].fillna('Desconhecida').value_counts()
    fig = px.pie(values=city_counts, names=city_counts.index, title='Distribuição por Cidade')
    return fig

@app.callback(
    Output('availability-distribution', 'figure'),
    Input('search-filter', 'value'),
    Input('city-filter', 'value'),
    Input('availability-filter', 'value'),
    Input('verification-filter', 'value'),
    Input('pet-filter', 'value')
)
def update_availability_distribution(search_filter, city_filter, availability_filter, verification_filter, pet_filter):
    dff = df.copy()
    if search_filter:
        dff = dff[dff.apply(lambda row: row.astype(str).str.contains(search_filter, case=False).any(), axis=1)]
    if 'Todas as Cidades' not in city_filter:
        dff = dff[dff['city'].isin(city_filter)]
    if 'Todos' not in availability_filter:
        dff = dff[dff['availability'].isin(availability_filter)]
    if verification_filter != 'Todos':
        dff = dff[dff['verified_status'] == verification_filter]
    if pet_filter != 'Todos':
        dff = dff[dff['petFriendly'] == pet_filter]
    availability_counts = dff['availability'].value_counts()
    fig = px.bar(x=availability_counts.index, y=availability_counts, title='Distribuição de Disponibilidade')
    return fig

if __name__ == '__main__':
    app.run_server(debug=False)
