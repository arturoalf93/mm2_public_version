# -*- coding: utf-8 -*-
"""
Created on Mon Jul 29 17:26:47 2019

@author: arodriguez
"""

# -*- coding: utf-8 -*-
import dash
import dash_core_components as dcc
#import custom_arturo_dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
import plotly.graph_objs as go
import pandas as pd
#from datetime import datetime
import datetime
from urllib.parse import unquote
from datetime import timedelta
import base64
import math
from urllib.parse import quote
import locale
import json
import os
import redis
import tasks
import requests


locale.setlocale(locale.LC_ALL, 'en_US')


################################ ENVIRONMENT VARIABLES ################################

on_heroku = os.environ.get("ON_HEROKU", 0)

if on_heroku:
    proxies = {
    "http": os.environ['QUOTAGUARDSTATIC_URL'],
    "https": os.environ['QUOTAGUARDSTATIC_URL']
    }
    
    res = requests.get("http://ip.quotaguard.com/", proxies=proxies)

    currency_symbol_dict = json.loads(os.environ['CURRENCY_SYMBOL_DICT'])
    defaults = json.loads(os.environ['DEFAULTS'])
    table_metals_list = json.loads(os.environ['TABLE_METALS_LIST'])['metals_list']
    
    redis_instance = redis.StrictRedis.from_url(os.environ.get("REDIS_URL"))
    
    external_stylesheets = json.loads(os.environ['EXTERNAL_STYLESHEETS'])['sheets_list']
    external_scripts = json.loads(os.environ['EXTERNAL_SCRIPTS'])['scripts_list']
    
else:
    currency_symbol_dict = {"USD": "$", "EUR":"€", "CNY":"¥", "KRW":"₩", "INR": "₹", "JPY":"¥" ,"GBP": "£"}
    defaults = {'Aluminum': ['LME', 'Primary 3 Month'],
            'Copper': ['LME', 'Primary 3 Month'],
            'Lead': ['LME', 'Primary 3 Month'],
            'Nickel': ['LME', 'Primary 3 Month'],
            'Tin': ['LME', 'Primary 3 Month'],
            'Zinc': ['LME', 'Primary 3 Month'],
            'Steel': ['United States', 'HRC'],
            'Scrap': ['United States', 'Total US Prompt Industrial Comp.'],
            'Precious & Minor Metals': ['LME', 'Cobalt Primary Cash']}
    table_metals_list = ['Aluminum', 'Copper', 'Lead', 'Nickel', 'Steel', 'Tin', 'Zinc']
    
    redis_instance = redis.StrictRedis.from_url('redis://127.0.0.1:6379')

    external_stylesheets = ['https://insights.metalminer.com/wp-content/themes/underboot/css/tableapp.css']
    external_scripts = ['https://insights.metalminer.com/wp-content/themes/underboot/js/custom-script.js']   

########################################################################################




###################################### FUNCTIONS ######################################


def get_date_updated():
    date_updated = redis_instance.hget( tasks.REDIS_HASH_NAME, "DATE_UPDATED").decode("utf-8")
    return date_updated

def get_metals_df():
    jsonified_df = redis_instance.hget(tasks.REDIS_HASH_NAME, "METALS_DF").decode("utf-8")
    metals_df = pd.DataFrame(json.loads(jsonified_df))
    return metals_df

def get_df_uniques():
    jsonified_df = redis_instance.hget(tasks.REDIS_HASH_NAME, 'df_uniques').decode("utf-8")
    df_uniques = pd.DataFrame(json.loads(jsonified_df))
    return df_uniques

def get_filtered_df(Type, country, form):
    sub_df = Type + '-' + country + '-' + form
    jsonified_df = redis_instance.hget(tasks.REDIS_HASH_NAME, sub_df).decode("utf-8")
    filtered_df = pd.DataFrame(json.loads(jsonified_df))
    filtered_df['collectionTime'] = pd.to_datetime(filtered_df['collectionTime'], format='%Y-%m-%d')
    filtered_df.sort_values(by=['Type', 'country', 'form', 'collectionTime'], ascending = [True, True, True, False], inplace = True)
    return filtered_df

def pretty(number):
    if float(number).is_integer():
        return number
    else:
        return round(number,2)

def separators(number):
    if abs(number) < 1000:
        return number
    elif abs(number) >=1000000:
        number = round(number/1000000,3)
        number = str(number) + 'M'
        return number
    elif abs(number) >=1000:
        number = int(number)
        number = locale.format("%d", number, grouping=True)
        return number
    
########################################################################################
        


############################### LT ST Heights and Widths ###############################

def px(height): return str(height) + 'px'

def transform(perc):
    if perc > 100: perc = 100
    elif perc < 0: perc = 0
    return [ (0.925-0.0085*perc)*img_h , 188-1.65*perc ]

def perc(current, support, resistance): return 100.0*(current-support)/(resistance-support)

lt_st_div_height = 263

img_h = 200
img_w = 80
img_top = -20

current_perc = 30 # THIS WILL BE THE VARIABLE NUMBER
current_bar_top, current_label_top = transform(current_perc)


sr_label_left = -8
sr_number_right = -8

upper_number_top = 0
upper_label_top = 14
lower_label_top = 0.98*img_h

########################################################################################



##################################### DYNAMIC CSS #####################################

mm_purple = "#52234B"
white = "#ffffff"
light_grey = "#F5F5F5"
dropdown_style = {'width': '31.33%', 'display': 'inline-block', 'textAlign': 'center', 'position': 'relative',
                  'top': '50%', 'transform': 'translateY(-50%)', 'z-index':'1',
                  'padding-left': '1%', 'padding-right': '1%'}
lt_st_style = {'display':'inline-block', 'width':'50%', 'background-color':'grey', 'font-size':'20px',
               'font-family':'HelveticaNeue', 'color':white,'font':'bold', 'text-align':'center'}

tabs_styles = { 'height': '30px'}

tab_style = {
   # 'borderBottom': '1px solid #d6d6d6',
    'padding': '5px',
   # 'fontWeight': 'bold'
}

tab_selected_style = {
    'borderTop': '2px solid ' + mm_purple,
   # 'borderBottom': '1px solid #d6d6d6',
   # 'backgroundColor': '#119DFF',
    'padding': '5px'
}

########################################################################################


app = dash.Dash(__name__, external_stylesheets=external_stylesheets, external_scripts = external_scripts, serve_locally=False)

app.config.suppress_callback_exceptions = True # so we can do multi-layouts
server = app.server


# initialize the data when the app starts
# DO NOT DO IT THIS WAY, DO IT THROUGH TASKS IN TASKS.PY, OR THE HEROKU 30 SEC TIMEOUT WILL SCREW EVERYTHING
#tasks.update_data(0)


if "DYNO" in os.environ:
    if bool(os.getenv("DASH_PATH_ROUTING", 0)):
        app.config.requests_pathname_prefix = "/{}/".format(os.environ["DASH_APP_NAME"])


app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    html.Div(id='page-content')
])

main_chart_layout =  html.Div(id='main_chart_frame', children = [ #h0
    #dcc.Location(id='url', refresh=False),
    html.Div(id='date_updated', className='a0'),
    html.Div(className='a1'), #h0.5
    html.Div([ #h1.1
            html.Div(id='title', children='-',
                   className = 'a2'
            ), #h2.1
            html.Div([ #h2.2
                    html.Div( #h3.1
                        html.Div( dcc.Dropdown(id='mm_country' , options=[], searchable = False, clearable = False)),
                        className = 'a3'
                    ), #h3.1
                    html.Div( #h3.2
                            html.Div(dcc.Dropdown(id='mm_form' , options = [], searchable = False, clearable = False)),
                            className = 'a4' 
                    ), #h3.2
                    html.Div( #h3.3
                            html.Div(dcc.Dropdown(id='mm_currency' ,
                                                  options = [{'label': key+' ('+currency_symbol_dict[key]+')', 'value': key} for key in currency_symbol_dict],
                                                  value = 'USD', 
                                                  searchable = False, clearable = False)),
                            className = 'a5',

                    ), #h3.3
                        html.A(
                            html.Button('Download\nCSV', className = 'a5p6'),
                            id='download-link',
                            download="empty.csv",
                            href="",
                            target="_blank",
                            className = 'a6'
                        )
            ],
            className ='a7'
            ), #h2.2
            dcc.Tabs(id='tabs', value = '6M', children = [dcc.Tab(label='6M', value='6M', style=tab_style, selected_style=tab_selected_style),
                                                          dcc.Tab(label='YTD', value='YTD', style=tab_style, selected_style=tab_selected_style ),
                                                          dcc.Tab(label='1Y', value='1Y', style=tab_style, selected_style=tab_selected_style),
                                                          dcc.Tab(label='3Y', value='3Y', style=tab_style, selected_style=tab_selected_style),
                                                          dcc.Tab(label='5Y', value='5Y', style=tab_style, selected_style=tab_selected_style),
                                                          dcc.Tab(label='Max', value='Max', style=tab_style, selected_style=tab_selected_style)],
                                            className = 'a8'),
            html.Div([
                html.Div(
                        dcc.Graph(id='line_graph', config = {'displaylogo':False, 'modeBarButtonsToRemove': ['resetScale2d', 'toggleSpikelines', 'toImage']}),
                        className = 'a9'
                )],
            className = 'a10'#h2.3
            )
    ],                        
    className = 'a11' #h1.1 style          
    ), #h1.1
    html.Div(className = 'a12'), #h1.5
    html.Div([ #h1.2,
            html.Div([
                    html.Div([
                            html.Div([
                                    html.Div(className = 'a13'),
                                    html.Div(id= 'current_price_label', children = 'Current Price',
                                             className = 'a14'),
                                    html.Div(id= 'current_date',
                                             className = 'a15')
                                    ], className = 'a16'),
                            html.Div([
                                html.Div(id= 'current_price',
                                         className = 'a17'),

                                html.Div(id ='24h_price_change_label', children = '24h Price Change', className = 'a18'),
                                html.Div([
                                         html.Div(id = 'img_container_pc', className = 'a19'),
                                         html.Div(className = 'a20'),
                                         html.Div(id='price_change', className = 'a21')
                                         ], className = 'a22')

                            ], className = 'a23')
                    ]), # h3.10
                    html.Div(className = 'a24'),
                    html.Div([
                            html.Div(id= '30_pc_label', children = '30 Days Price Change', className = 'a25'),
                            html.Div([
                                html.Div(id = 'img_container_30', className = 'a26'),
                                html.Div(className = 'a27'),
                                html.Div(id= '30_pc', className = 'a28'),
                                html.Div(className = 'a27'),         
                                html.Div(id='30_pc_perc', className = 'a29')
                            ], className = 'a30')
                    ])
            ]),
                    html.Div(className = 'a31'),
                    html.Div(id='LTST')
    ],    className = 'a32' #h1.2
    ), #h1.2 
    html.Div(className = 'a33'), #h2.5
], className = 'a34') #h0
                            
    
@app.callback([
            Output('date_updated','children'),
            Output('line_graph','figure'), Output('title','children'), Output('current_date', 'children'),
            Output('current_price','children'), Output('price_change', 'children'), Output('img_container_pc','children'),
            Output('img_container_30','children'), Output('30_pc','children'), Output('30_pc_perc','children'),
            Output('LTST','children'), Output('download-link', 'download'), Output('download-link', 'href')],
            [Input('mm_form','value'), Input('mm_currency','value'),Input('tabs','value')],
            [State('url','pathname'), State('mm_country','value')])
def update_charts(form, currency, tab, Type, country):
    '''
    # DO NOT ENABLE UPDATE ENDPOINT, NOT SECURE
    if Type != None:
        Type = unquote(Type[1:])
        if Type == 'update' or Type == 'Update':
            tasks.update_data(2)
            return ['','', '', '', '%', '', '', '%', '', '', '', '', '']
    '''
    
    print('---------> Enters in callback 3, before entering in get_data(). Type, country, form:', Type, country, form, datetime.datetime.now())
    if Type != None and country != None and form != None and form != '':
        Type = unquote(Type[1:])
        if Type == 'Table':
            raise PreventUpdate
        
        currency_symbol = currency_symbol_dict[currency]        
        date_updated = get_date_updated()
        metals_df = get_metals_df()
        df_filtered = get_filtered_df(Type, country, form)
        perUnit = df_filtered.perUnit.unique()[0]

        title = Type + ' ' + country + ' ' + form + ' (' + currency_symbol_dict[currency] + ')'
        if len(title)>=43:
            title = title[:40]+'...'
        max_date = df_filtered['collectionTime'].max()

        first_date_dict = {'6M':183, '1Y':365, '3Y':365*3, '5Y':365*5}
        if tab  in first_date_dict.keys():
            first_date = max_date - timedelta(first_date_dict[tab])
        elif tab == 'YTD':
            first_date = datetime.datetime(int(max_date.strftime('%Y')),1,1)
        elif tab == 'Max':
            first_date = df_filtered['collectionTime'].min()
        
        dates = df_filtered.collectionTime
        df_y = df_filtered[currency]
        
        data = [{'x': dates, 'y': df_y, 'marker': {'size': 5,'color':mm_purple}, 'name':''}]

        current_price = df_filtered[df_filtered['collectionTime'] == max_date][currency].tolist()[0]

        current_price_rounded = pretty(current_price)
        current_price_rounded = separators(current_price_rounded)
        current_date = max_date.strftime('%b %d, %Y')
        
        last_day_date = max_date - timedelta(1)
        if df_filtered[df_filtered['collectionTime']==last_day_date].empty:
            last_day_date = max_date - timedelta(2)
            if df_filtered[df_filtered['collectionTime']==last_day_date].empty:
                last_day_date = max_date - timedelta(3)
        try:
            price_change = current_price - df_filtered[df_filtered['collectionTime']==(last_day_date)].iloc[0][currency]
            price_change = pretty(price_change)
            price_change_pretty = separators(price_change)
            price_change_to_show = currency_symbol + str(price_change_pretty)
        except IndexError:
            price_change = '-'
            price_change_to_show = '-'

        last_30_date = max_date - timedelta(30)

        price_30_d_ago = df_filtered[df_filtered['collectionTime']==(last_30_date)][currency].tolist()[0]
        last_30_pc = current_price - price_30_d_ago
        last_30_pc_perc = 100 * last_30_pc / price_30_d_ago

        last_30_pc_rounded = pretty(last_30_pc)
        last_30_pc_perc_rounded = pretty(last_30_pc_perc)
        last_30_pc_pretty = separators(last_30_pc_rounded)

        if price_change == 0 or price_change == '-':
            img_container = ''
        else:
            if price_change < 0:
                image_name = 'assets/red_triangle.png'
            elif price_change > 0:
                image_name = 'assets/green_triangle.png'
            encoded_image = base64.b64encode(open(image_name, 'rb').read())
            img_container = html.Img(src='data:/;base64,{}'.format(encoded_image.decode()), className = 'a35')

        if last_30_pc_rounded == 0:
            img_container_30 = ''
        else:
            if last_30_pc_rounded < 0:
                image_name_30 = 'assets/red_triangle.png'
            elif last_30_pc_rounded > 0:
                image_name_30 = 'assets/green_triangle.png'
            encoded_image = base64.b64encode(open(image_name_30, 'rb').read())
            img_container_30 = html.Img(src='data:/;base64,{}'.format(encoded_image.decode()), className = 'a36')

        metals_df_filtered = metals_df[(metals_df['Type']==Type) &  (metals_df['country'] ==country) & (metals_df['form']== form)]

        lt_support = metals_df_filtered['lt_support_' + currency].tolist()[0]
        lt_resistance = metals_df_filtered['lt_resistance_' + currency].tolist()[0]
        st_support = metals_df_filtered['st_support_' + currency].tolist()[0]
        st_resistance = metals_df_filtered['st_resistance_' + currency].tolist()[0]
        
        if math.isnan(st_support) or math.isnan(st_resistance):
            xaxis_range = [first_date, max_date]
        else:
            xaxis_range = [first_date, max_date+timedelta(31)]
            sr_x = []
            st_resistance_y = []
            st_support_y = []
            for i in range(63):
                sr_x.append((max_date - timedelta(-31+i)).strftime('%Y-%m-%d'))
                st_resistance_y.append(st_resistance)
                st_support_y.append(st_support)

            data.append( {'x': sr_x, 'y': st_resistance_y, 'marker': {'size': 5,'color':'red'}, 'name':'Resistance'} )
            data.append( {'x': sr_x, 'y': st_support_y, 'marker': {'size': 5,'color':'green'}, 'name':'Support'} )
            

        if math.isnan(st_support) or math.isnan(st_resistance):
            LTST = html.Div()
        else:
            if math.isnan(lt_support) or math.isnan(lt_resistance):
                lt_display_style = {'display':'none'}
            else:
                lt_display_style = {}

            lt_support = pretty(lt_support)
            lt_resistance = pretty(lt_resistance)
            
            st_support = pretty(st_support)
            st_resistance = pretty(st_resistance)

            
            encoded_image = base64.b64encode(open('assets/background.png', 'rb').read())
            img_container_background = html.Img(src='data:/;base64,{}'.format(encoded_image.decode()), style={'width':px(img_w), 'height':px(img_h), 'position':'absolute', 'z-index':'1'})
    
            encoded_image = base64.b64encode(open('assets/bar.png', 'rb').read())
            lt_current_perc = perc(current_price, lt_support, lt_resistance)
            lt_current_bar_top, lt_current_label_top = transform(lt_current_perc)  
            lt_img_container_bar = html.Img(src='data:/;base64,{}'.format(encoded_image.decode()), style={'position':'absolute', 'z-index':'2', 'width':px(.8*img_w), 'height':'3px', 'top':px(lt_current_bar_top)})
    
            st_current_perc = perc(current_price, st_support, st_resistance)
            st_current_bar_top, st_current_label_top = transform(st_current_perc)
    
            st_img_container_bar = html.Img(src='data:/;base64,{}'.format(encoded_image.decode()), style={'position':'absolute', 'z-index':'2', 'width':px(.8*img_w), 'height':'3px', 'top':px(st_current_bar_top)})
    
            lt_current_label_style = {'position':'relative', 'top':px(lt_current_label_top), 'z-index':'3'}
            lt_current_price_style = {'position':'relative', 'top':px(lt_current_label_top), 'z-index':'3'}
    
            st_current_label_style = {'position':'relative', 'top':px(st_current_label_top), 'z-index':'3'}
            st_current_price_style = {'position':'relative', 'top':px(st_current_label_top), 'z-index':'3'}
                    
            lt_support = separators(lt_support)
            lt_resistance = separators(lt_resistance)
            st_support = separators(st_support)
            st_resistance = separators(st_resistance) 
            LTST =  html.Div([
                        html.Div(id= 'sr_label', children = 'Support / Resistance',
                                 className = 'a37'),
                        html.Div([
                                html.Div('Short Term',className = 'a38'),
                                html.Div('Long Term',className = 'a38', style = lt_display_style)
                                ]),
                        html.Div([
                                    html.Div(className = 'a39'),
                                    html.Div([
                                            html.Div([html.Div(id='st_resistance', children =currency_symbol + str(st_resistance), className = 'a50'),
                                                      html.Div('.', className = 'a41'),
                                                      html.Div(id='st_support', children=currency_symbol + str(st_support), className = 'a51')],
                                                className = 'a43'),
                                            html.Div(id = 'img_container_st', children=[img_container_background,st_img_container_bar], className = 'a44'),
                                            html.Div([html.Div('Resistance', className = 'a45'),
                                                      html.Div(id='st_current_label', children='Current', style = st_current_label_style),
                                                      html.Div(id='st_current_price', children=currency_symbol + str(current_price_rounded), style = st_current_price_style),
                                                      html.Div('Support',className = 'a46')],
                                               className = 'a47')
                                    ],className = 'a48', style={}),                                    
                                    html.Div(className = 'a49'),                                       
                                    html.Div([
                                            html.Div([html.Div(id='lt_resistance', children=currency_symbol + str(lt_resistance),  className = 'a40'),
                                                      html.Div('.', className = 'a41'),
                                                      html.Div(id='lt_support', children=currency_symbol + str(lt_support), className = 'a42')],
                                                className = 'a43'),
                                            html.Div(id = 'img_container_lt', children=[img_container_background, lt_img_container_bar], className = 'a44'),
                                            html.Div([html.Div('Resistance', className = 'a45'),
                                                      html.Div(id='lt_current_label', children = 'Current', style =lt_current_label_style),
                                                      html.Div(id='lt_current_price',children=currency_symbol + str( current_price_rounded ), style =lt_current_price_style),
                                                      html.Div('Support', className = 'a46')],
                                                className = 'a47')
                                    ],className = 'a48', style = lt_display_style),
                                    html.Div(className = 'a49')
                                    ],className = 'a52')
                    ])
                                
        csv_title = Type + '_' + country + '_' + form + '.csv'     
        csv_title = csv_title.replace(' ', '_')                   
        csv_string = df_filtered.to_csv(index=False, encoding='utf-8')
        csv_string = "data:text/csv;charset=utf-8," + quote(csv_string)

        return [
                date_updated,
                {'data':data,'layout': go.Layout(xaxis= {'range': xaxis_range}, margin={'t':30, 'l':50, 'r':30, 'b':30}, showlegend = False)},
                title,
                 'as of ' + str(current_date),
                 currency_symbol + str(current_price_rounded) + ' ' + '/' + perUnit,
                 price_change_to_show,
                 img_container,
                 img_container_30,
                 currency_symbol + str(last_30_pc_pretty),
                 '(' + str(abs(last_30_pc_perc_rounded)) + '%)',
                 LTST,
                 csv_title,
                 csv_string
                 ]
    else:  
        raise PreventUpdate
    
    
@app.callback([Output('mm_form', 'options'),Output('mm_form', 'value')],
               [Input('mm_country','value')],[State('url','pathname') ])
def update_mm_form(country , Type):
    print('---------> Enters in Callback 2. Type, country:', Type, country, datetime.datetime.now())
    if Type == None or Type == '' or country == None:
        raise PreventUpdate
        #return [[],'']
    Type = unquote(Type[1:])
    if Type == 'Table':
        raise PreventUpdate
    if Type == 'update' or Type == 'Update':
        return [[],'']
    
    df_uniques = get_df_uniques()

    form = sorted(df_uniques[(df_uniques['Type'] == Type) & (df_uniques['country'] == country)]['form'].unique())
    if defaults[Type][0] == country: # so the chart by default loads when refreshing
        value = defaults[Type][1]
    else:
        value = form[0]
    return [[{'label': i, 'value': i} for i in form], value]


@app.callback([Output('page-content', 'children'),Output('mm_country', 'options'),Output('mm_country', 'value')],
              [Input('url', 'pathname')])
def display_page(pathname):
    print('--------->Enters in Callback 1. pathname:', pathname, datetime.datetime.now())
    if pathname == None or pathname == '':
        raise PreventUpdate
        
    pathname = unquote(pathname[1:])

    if pathname == 'Table':
        
        metals_current_prices = {}
        metals_units = {}
        
        for Type in table_metals_list:
            country = defaults[Type][0]
            form = defaults[Type][1]
            df_filtered = get_filtered_df(Type, country, form)
            max_date = df_filtered['collectionTime'].max()
            current_price = df_filtered[df_filtered['collectionTime'] == max_date]['USD'].tolist()[0]
            perUnit = df_filtered.perUnit.unique()[0]
            
            metals_current_prices[Type] = current_price
            metals_units[Type] = perUnit
            
        main_table_layout = html.Div(children =
                [html.Div([
                    html.Div(id= Type, children = '$' + str(metals_current_prices[Type]) + ' /' + metals_units[Type], className = 't1'),
                    html.Div(className = 't2')
                ])
                for Type in table_metals_list],
                className = 't3'
                                     )
        return [main_table_layout, [], '']
    
    elif pathname == 'yvanehtnioj':
        df_filtered = get_filtered_df('Aluminum', 'LME', 'Primary 3 Month')
        test = int(df_filtered[df_filtered['collectionTime'] == '2019-09-02']['USD'])
        print(test)
        to_test_layout = html.Div(className = 'nchk', children = test)
        return [to_test_layout, [], '']
  
    else:
        Type = pathname
        df_uniques = get_df_uniques()

        country = sorted(df_uniques[df_uniques['Type'] == Type]['country'].unique())
        value = defaults[Type][0]
        return [main_chart_layout,[{'label': i, 'value': i} for i in country], value]

if __name__ == '__main__':
    app.run_server(debug=False)
    #app.serve_component_suites = True