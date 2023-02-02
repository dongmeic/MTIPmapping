import json, re
from urllib.request import urlopen
from sqlalchemy import create_engine
from geopy.geocoders import ArcGIS
import geopandas as gpd
import pandas as pd

path = r'T:\MPO\TIP\TIP FY24-27\Maps\Data'

# read data from RLIDgeo
engine = create_engine(   
"mssql+pyodbc:///?odbc_connect="
"Driver%3D%7BODBC+Driver+17+for+SQL+Server%7D%3B"
"Server%3Drliddb.int.lcog.org%2C5433%3B"
"Database%3DRLIDGeo%3B"
"Trusted_Connection%3Dyes%3B"
"ApplicationIntent%3DReadWrite%3B"
"WSID%3Dclwrk4087.int.lcog.org%3B")

rep_sql = '''
SELECT 
repdist AS id,
repname AS name,
Shape.STAsBinary() AS geometry
FROM dbo.StateRepDist;
'''
sen_sql = '''
SELECT 
sendist AS id,
senname AS name,
Shape.STAsBinary() AS geometry
FROM dbo.StateSenDist;
'''


def write_json(url_string, filename):
    response = urlopen(url_string)
    data = response.read()
    txt_str = data.decode('utf-8')
    lines = txt_str.split("\r\n")
    file = path + '\\' + filename + '.json'
    fx = open(file, "w")
    for line in lines:
        fx.write(line+ "\n")
    fx.close()

def json2shp(filename):
    file = path + '\\' + filename + '.json'
    arcpy.JSONToFeatures_conversion(file, filename)

# points in polygons
def get_pip(points, polygon):
    id_list = list(polygon.id)
    df = pd.DataFrame().reindex_like(points).dropna()
    for ID in id_list:
        pol = (polygon.loc[polygon.id==ID])
        pol.reset_index(drop = True, inplace = True)
        pip_mask = points.within(pol.loc[0, 'geometry'])
        pip_data = points.loc[pip_mask].copy()
        pip_data['id']= ID
        df = df.append(pip_data)
    df.reset_index(inplace=True, drop=True)
    df = df.drop(columns='geometry')
    return df    
    
def getAQvars(x, var=['AQ Exempt?', 'AQ Status', 'IAC']):
    if str(x) == 'nan':
        res = None
    elif var == 'AQ Exempt?':
        if 'EXEMPT' in x:
            res = 'Yes'
        else:
            res = 'No'
    
    elif var == 'IAC':
        if 'IAC' in x:
            res = 'IAC ' + x.split(' (IAC ')[1].split(')')[0]
        else:
            res = 'N/A'
    
    elif var == 'AQ Status':
        if 'EXEMPT' in x:
            if 'IAC' in x:
                res = x.split('EXEMPT / ')[1].split(' (IAC')[0]
            else:
                res = x.split('EXEMPT / ')[1]
        elif 'IAC' in x:
            res = x.split(' (IAC')[0]
        else:
            res = x
    
    return res

def reorder(x):
    if len(x) >= 4:
        if ',' in re.search(r',', x).group():
            res = ', '.join(str(x) for x in sorted([eval(i) for i in x.split(', ')]))
        else:
            res = x
    else:
        res = x
    return res

# dat=points
# shptype='point', keycol='STIP_Key'
# colnm1='Senator District', colnm2='Representative District'
def get_district_IDs(dat,
                     shptype,
                     keycol,
                     colnm1,
                     colnm2):
    
    StateRepDist = readRepDist()
    StateSenDist = readSenDist()
    ply1=StateSenDist
    ply2=StateRepDist
    
    if shptype=='point':
        joined1 = get_pip(dat, ply1)
        joined2 = get_pip(dat, ply2)
    
    else:
        joined1 = gpd.sjoin(dat, ply1)
        joined2 = gpd.sjoin(dat, ply2)    
    
    joined1.rename(columns={'id':colnm1}, inplace=True)
    joined2.rename(columns={'id':colnm2}, inplace=True)

    joined1.drop_duplicates(ignore_index=True, inplace=True)
    joined2.drop_duplicates(ignore_index=True, inplace=True)

    joined1m = joined1[[keycol, colnm1]].groupby(keycol)[colnm1].apply(', '.join).reset_index()
    joined2m = joined2[[keycol, colnm2]].groupby(keycol)[colnm2].apply(', '.join).reset_index()
    joined_c = joined1m.merge(joined2m, on=keycol)
    
    joined_c[colnm1] = joined_c[colnm1].apply(reorder)
    joined_c[colnm2] = joined_c[colnm2].apply(reorder)
    
    return joined_c

def getCoordinates(address):
    lonlat = ArcGIS().geocode(address)
    #latitude = lonlat[1][0]
    #longitude = lonlat[1][1]
    (latitude, longitude) = lonlat[1]
    return [address, longitude, latitude] 

def getLonLat(x):
    return x.replace('(','').replace(')','').split(', ')

def readRepDist():
    StateRepDist = gpd.GeoDataFrame.from_postgis(rep_sql, engine, geom_col='geometry')
    StateRepDist.crs = "EPSG:2914"
    StateRepDist = StateRepDist.to_crs(epsg=2992)
    return StateRepDist

def readSenDist():
    StateSenDist = gpd.GeoDataFrame.from_postgis(sen_sql, engine, geom_col='geometry')
    StateSenDist.crs = "EPSG:2914"
    StateSenDist = StateSenDist.to_crs(epsg=2992)
    return StateSenDist