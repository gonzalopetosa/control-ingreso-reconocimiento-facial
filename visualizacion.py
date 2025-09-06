import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Para evitar problemas con hilos en Flask
from flask import Flask, render_template, Blueprint
import io
import base64
from datetime import datetime
from decorators import facial_auth_required, role_required

# --- 1. Inicialización de la Aplicación Flask ---
app = Flask(__name__)

visualizacion_bp = Blueprint("visualizacion", __name__)

# --- 2. Carga de los Datasets en Memoria ---
# Para eficiencia, cargamos los CSV una sola vez cuando la app se inicia.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "Data")
dataframes = {}

# Diccionario para mapear nombres amigables a los archivos CSV
files = {
    'ingresos_egresos': 'ingresos_egresos.csv',
    'autorizaciones': 'autorizaciones.csv',
    'produccion': 'produccion.csv',
    'proveedores': 'proveedores.csv',
    'stock': 'stock.csv',
    'trazabilidad': 'trazabilidad_lotes.csv',
    'transporte': 'carga_transporte.csv'
}

# Bucle para leer cada archivo y guardarlo en el diccionario de dataframes
for name, filename in files.items():
    try:
        # Leemos el contenido del archivo desde la cadena proporcionada
        if name == 'produccion':
            # Para el archivo de producción, necesitamos convertir las fechas
            content = globals().get(f"{name}_content", "")
            if content:
                dataframes[name] = pd.read_csv(io.StringIO(content), parse_dates=['fecha'], dayfirst=True)
            else:
                # Cargar desde archivo si no hay contenido en variable
                path = os.path.join(DATA_DIR, filename)
                dataframes[name] = pd.read_csv(path, parse_dates=['fecha'], dayfirst=True)
        else:
            content = globals().get(f"{name}_content", "")
            if content:
                dataframes[name] = pd.read_csv(io.StringIO(content))
            else:
                path = os.path.join(DATA_DIR, filename)
                dataframes[name] = pd.read_csv(path)

        print(f"✅ Dataset '{filename}' cargado correctamente.")
    except Exception as e:
        print(f"❌ Error cargando '{filename}': {str(e)}")

# --- 3. Procesamiento de Datos para Análisis de Desperdicios ---
def procesar_datos_desperdicios():
    if 'produccion' not in dataframes:
        return None

    # Calcular el desperdicio total por producto
    desperdicio_por_producto = dataframes['produccion'].groupby('producto')['desperdicio'].sum().reset_index()

    # Ordenar de mayor a menor desperdicio
    desperdicio_por_producto = desperdicio_por_producto.sort_values('desperdicio', ascending=False)

    return desperdicio_por_producto

# --- 4. Rutas de la Aplicación Flask ---
@visualizacion_bp.route('/')
@facial_auth_required
@role_required("ADMIN")
def index():
    # Obtener datos OEE para mostrar en el dashboard
    df_oee = calcular_oee()

    if df_oee is not None:
        # Calcular OEE promedio
        oee_promedio = df_oee['OEE'].mean() * 100

        # Preparar gráfico OEE
        plt.figure(figsize=(8, 4))
        bars = plt.bar(df_oee["turno"] + " " + df_oee["fecha"].dt.strftime("%d-%m"), df_oee["OEE"]*100, color="royalblue")
        plt.title("OEE por Turno", fontsize=14)
        plt.ylabel("OEE (%)")
        plt.xticks(rotation=45)

        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height,
                     f"{height:.1f}%", ha="center", va="bottom")

        img = io.BytesIO()
        plt.savefig(img, format="png", bbox_inches="tight")
        img.seek(0)
        oee_plot_url = base64.b64encode(img.getvalue()).decode()
        plt.close()

        # Preparar datos para la tabla
        oee_data = df_oee.to_dict('records')

        return render_template('index.html',
                              oee_value="%.1f" % oee_promedio,
                              oee_plot_url=oee_plot_url,
                              oee_data=oee_data)
    else:
        # Si no hay datos OEE, mostrar valores por defecto
        return render_template('index.html',
                              oee_value="N/A",
                              oee_plot_url="",
                              oee_data=[])

@visualizacion_bp.route('/desperdicios')
@facial_auth_required
@role_required("ADMIN")
def mostrar_desperdicios():
    # Procesar datos de desperdicios
    datos_desperdicios = procesar_datos_desperdicios()

    if datos_desperdicios is None:
        return "Datos de producción no disponibles", 500

    # Crear gráfico de torta
    plt.figure(figsize=(10, 8))

    # Usar colores distintos para cada segmento
    colors = plt.cm.Set3(range(len(datos_desperdicios)))

    # Crear el gráfico de torta
    plt.pie(datos_desperdicios['desperdicio'],
            labels=datos_desperdicios['producto'],
            autopct='%1.1f%%',
            startangle=90,
            colors=colors)

    plt.title('Distribución de Desperdicios por Producto', fontsize=16)
    plt.axis('equal')  # Asegura que el gráfico sea circular

    # Convertir gráfico a imagen base64
    img = io.BytesIO()
    plt.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode()
    plt.close()

    # Crear también un gráfico de barras para comparación
    plt.figure(figsize=(12, 6))
    bars = plt.bar(datos_desperdicios['producto'], datos_desperdicios['desperdicio'], color=colors)
    plt.title('Cantidad de Desperdicio por Producto (KG)', fontsize=16)
    plt.xlabel('Producto')
    plt.ylabel('Desperdicio (KG)')
    plt.xticks(rotation=45, ha='right')

    # Añadir valores en las barras
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.2f} KG',
                ha='center', va='bottom')

    img2 = io.BytesIO()
    plt.savefig(img2, format='png', bbox_inches='tight')
    img2.seek(0)
    plot_url2 = base64.b64encode(img2.getvalue()).decode()
    plt.close()

    # Preparar datos para la tabla
    tabla_datos = datos_desperdicios.to_dict('records')

    return render_template('desperdicios.html',
                          plot_url=plot_url,
                          plot_url2=plot_url2,
                          tabla_datos=tabla_datos)



def procesar_horas_trabajadas():
    if 'ingresos_egresos' not in dataframes:
        return None

    df = dataframes['ingresos_egresos'].copy()

    # Convertir horas a datetime y calcular diferencia
    df['hora_ingreso'] = pd.to_datetime(df['hora_ingreso'], format='%H:%M')
    df['hora_egreso'] = pd.to_datetime(df['hora_egreso'], format='%H:%M')
    df['horas_trabajadas'] = (df['hora_egreso'] - df['hora_ingreso']).dt.total_seconds() / 3600

    # Agrupar por empleado
    horas_por_empleado = df.groupby(['id_empleado', 'nombre'])['horas_trabajadas'].sum().reset_index()

    return horas_por_empleado

@visualizacion_bp.route('/horarios')
@facial_auth_required
@role_required("ADMIN")
def mostrar_horarios():
    datos_horas = procesar_horas_trabajadas()

    if datos_horas is None:
        return "Datos de ingresos/egresos no disponibles", 500

    # Crear gráfico de barras
    plt.figure(figsize=(12, 8))
    bars = plt.bar(datos_horas['nombre'], datos_horas['horas_trabajadas'], color='skyblue')
    plt.title('Horas Trabajadas por Empleado (23/08/2025)', fontsize=16)
    plt.xlabel('Empleado')
    plt.ylabel('Horas Trabajadas')
    plt.xticks(rotation=45)

    # Añadir valores en las barras
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.2f} h',
                ha='center', va='bottom')

    plt.tight_layout()

    # Convertir gráfico a imagen base64
    img = io.BytesIO()
    plt.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode()
    plt.close()

    return render_template('horarios.html', plot_url=plot_url, datos=datos_horas.to_dict('records'))

# Función para procesar datos de stock
def procesar_datos_stock():
    if 'stock' not in dataframes:
        return None, None, None, None

    df = dataframes['stock'].copy()

    # Convertir fechas a formato datetime
    df['fecha_ingreso'] = pd.to_datetime(df['fecha_ingreso'], dayfirst=True)
    df['fecha_vencimiento'] = pd.to_datetime(df['fecha_vencimiento'], dayfirst=True)

    # Calcular días hasta vencimiento
    hoy = pd.to_datetime('2025-08-23')  # Fecha de referencia (usar datetime.now() en producción)
    df['dias_hasta_vencer'] = (df['fecha_vencimiento'] - hoy).dt.days

    # Categorizar productos por proximidad al vencimiento
    def categorizar_vencimiento(dias):
        if dias < 0:
            return 'Vencido'
        elif dias < 30:
            return 'Por vencer (≤30 días)'
        elif dias < 90:
            return 'Próximo a vencer (31-90 días)'
        else:
            return 'Vigente (>90 días)'

    df['estado_vencimiento'] = df['dias_hasta_vencer'].apply(categorizar_vencimiento)

    # Agrupar por tipo de producto
    stock_por_producto = df.groupby('nombre_item')['cantidad (KG)'].sum().reset_index()

    # Productos próximos a vencer (30 días o menos)
    productos_proximos_vencer = df[df['dias_hasta_vencer'] <= 30].copy()

    # Agrupar por proveedor
    stock_por_proveedor = df.groupby('proveedor_id')['cantidad (KG)'].sum().reset_index()

    # Combinar con datos de proveedores si está disponible
    if 'proveedores' in dataframes:
        stock_por_proveedor = stock_por_proveedor.merge(
            dataframes['proveedores'][['proveedor_id', 'nombre']],
            on='proveedor_id',
            how='left'
        )

    return stock_por_producto, productos_proximos_vencer, stock_por_proveedor, df

# Ruta para el control de inventario
@visualizacion_bp.route('/inventario')
@facial_auth_required
def mostrar_inventario():
    stock_producto, productos_proximos, stock_proveedor, df_stock = procesar_datos_stock()

    if stock_producto is None:
        return "Datos de stock no disponibles", 500

    # Gráfico 1: Stock por tipo de producto
    plt.figure(figsize=(10, 6))
    bars = plt.bar(stock_producto['nombre_item'], stock_producto['cantidad (KG)'], color='lightgreen')
    plt.title('Cantidad de Stock por Tipo de Producto (KG)', fontsize=16)
    plt.xlabel('Tipo de Producto')
    plt.ylabel('Cantidad (KG)')
    plt.xticks(rotation=45)

    # Añadir valores en las barras
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}',
                ha='center', va='bottom')

    plt.tight_layout()
    img1 = io.BytesIO()
    plt.savefig(img1, format='png')
    img1.seek(0)
    plot_url1 = base64.b64encode(img1.getvalue()).decode()
    plt.close()

    # Gráfico 2: Distribución por estado de vencimiento
    estado_counts = df_stock['estado_vencimiento'].value_counts()
    plt.figure(figsize=(8, 8))
    colors = ['#ff6b6b', '#ffa726', '#42a5f5', '#66bb6a']
    plt.pie(estado_counts.values, labels=estado_counts.index, autopct='%1.1f%%', colors=colors)
    plt.title('Distribución de Stock por Estado de Vencimiento', fontsize=16)
    img2 = io.BytesIO()
    plt.savefig(img2, format='png')
    img2.seek(0)
    plot_url2 = base64.b64encode(img2.getvalue()).decode()
    plt.close()

    # Gráfico 3: Stock por proveedor
    plt.figure(figsize=(10, 6))
    if 'nombre' in stock_proveedor.columns:
        labels = stock_proveedor['nombre']
    else:
        labels = stock_proveedor['proveedor_id'].astype(str)

    bars = plt.bar(labels, stock_proveedor['cantidad (KG)'], color='orange')
    plt.title('Cantidad de Stock por Proveedor (KG)', fontsize=16)
    plt.xlabel('Proveedor')
    plt.ylabel('Cantidad (KG)')
    plt.xticks(rotation=45)

    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}',
                ha='center', va='bottom')

    plt.tight_layout()
    img3 = io.BytesIO()
    plt.savefig(img3, format='png')
    img3.seek(0)
    plot_url3 = base64.b64encode(img3.getvalue()).decode()
    plt.close()

    # Preparar datos para tablas
    tabla_stock = df_stock.to_dict('records')
    tabla_proximos = productos_proximos.to_dict('records')

    # Calcular resumen estadístico
    total_stock = df_stock['cantidad (KG)'].sum()
    productos_vencidos = len(df_stock[df_stock['dias_hasta_vencer'] < 0])
    productos_por_vencer = len(productos_proximos)

    return render_template('inventario.html',
                          plot_url1=plot_url1,
                          plot_url2=plot_url2,
                          plot_url3=plot_url3,
                          tabla_stock=tabla_stock,
                          tabla_proximos=tabla_proximos,
                          total_stock=total_stock,
                          productos_vencidos=productos_vencidos,
                          productos_por_vencer=productos_por_vencer)

def calcular_oee():
    try:
        # Cargar datasets
        tiempos = pd.read_csv(os.path.join(DATA_DIR, "tiempos_produccion.csv"), parse_dates=["fecha"])
        produccion = pd.read_csv(os.path.join(DATA_DIR, "produccion_velocidad.csv"), parse_dates=["fecha"])
        calidad = pd.read_csv(os.path.join(DATA_DIR, "calidad.csv"), parse_dates=["fecha"])

        # Merge por fecha y turno
        df = tiempos.merge(produccion, on=["fecha", "turno"]).merge(calidad, on=["fecha", "turno"])

        # Calcular métricas
        df["Disponibilidad"] = df["tiempo_operativo_min"] / df["tiempo_planificado_min"]
        df["Rendimiento"] = df["unidades_producidas"] / (df["tiempo_operativo_min"] * df["velocidad_ideal_upm"])
        df["Calidad"] = (df["unidades_totales"] - df["unidades_defectuosas"]) / df["unidades_totales"]
        df["OEE"] = df["Disponibilidad"] * df["Rendimiento"] * df["Calidad"]

        # Añadir campo velocidad_real_upm si no existe (para evitar error en template)
        if 'velocidad_real_upm' not in df.columns:
            df['velocidad_real_upm'] = df['unidades_producidas'] / (df['tiempo_operativo_min'] / 60)

        return df
    except Exception as e:
        print(f"Error al calcular OEE: {e}")
        return None

@visualizacion_bp.route("/oee")
@facial_auth_required
@role_required("ADMIN")
def mostrar_oee():
    df = calcular_oee()
    if df is None:
        return "No se pudo calcular OEE", 500

    # Calcular promedios
    disponibilidad_promedio = df["Disponibilidad"].mean()
    rendimiento_promedio = df["Rendimiento"].mean()
    calidad_promedio = df["Calidad"].mean()
    oee_promedio = df["OEE"].mean()

    # Gráfico principal OEE
    plt.figure(figsize=(12, 6))
    bars = plt.bar(df["turno"] + " " + df["fecha"].dt.strftime("%d-%m"), df["OEE"]*100,
                   color=["royalblue" if x >= 0.85 else "orange" if x >= 0.65 else "red" for x in df["OEE"]])
    plt.title("Indicador OEE por Turno", fontsize=16)
    plt.ylabel("OEE (%)")
    plt.axhline(y=85, color='green', linestyle='--', alpha=0.7, label='Excelente (85%)')
    plt.axhline(y=65, color='orange', linestyle='--', alpha=0.7, label='Aceptable (65%)')
    plt.legend()
    plt.xticks(rotation=45)

    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                 f"{height:.1f}%", ha="center", va="bottom")

    img = io.BytesIO()
    plt.savefig(img, format="png", bbox_inches="tight")
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode()
    plt.close()

    # Gráfico de Disponibilidad
    plt.figure(figsize=(10, 5))
    bars = plt.bar(df["turno"] + " " + df["fecha"].dt.strftime("%d-%m"), df["Disponibilidad"]*100, color="lightblue")
    plt.title("Disponibilidad por Turno", fontsize=14)
    plt.ylabel("Disponibilidad (%)")
    plt.xticks(rotation=45)

    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                 f"{height:.1f}%", ha="center", va="bottom")

    img_disp = io.BytesIO()
    plt.savefig(img_disp, format="png", bbox_inches="tight")
    img_disp.seek(0)
    plot_disponibilidad = base64.b64encode(img_disp.getvalue()).decode()
    plt.close()

    # Gráfico de Rendimiento
    plt.figure(figsize=(10, 5))
    bars = plt.bar(df["turno"] + " " + df["fecha"].dt.strftime("%d-%m"), df["Rendimiento"]*100, color="lightgreen")
    plt.title("Rendimiento por Turno", fontsize=14)
    plt.ylabel("Rendimiento (%)")
    plt.xticks(rotation=45)

    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                 f"{height:.1f}%", ha="center", va="bottom")

    img_rend = io.BytesIO()
    plt.savefig(img_rend, format="png", bbox_inches="tight")
    img_rend.seek(0)
    plot_rendimiento = base64.b64encode(img_rend.getvalue()).decode()
    plt.close()

    # Gráfico de Calidad
    plt.figure(figsize=(10, 5))
    bars = plt.bar(df["turno"] + " " + df["fecha"].dt.strftime("%d-%m"), df["Calidad"]*100, color="gold")
    plt.title("Calidad por Turno", fontsize=14)
    plt.ylabel("Calidad (%)")
    plt.xticks(rotation=45)

    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                 f"{height:.1f}%", ha="center", va="bottom")

    img_cal = io.BytesIO()
    plt.savefig(img_cal, format="png", bbox_inches="tight")
    img_cal.seek(0)
    plot_calidad = base64.b64encode(img_cal.getvalue()).decode()
    plt.close()

    # Gráfico de Evolución del OEE
    df_sorted = df.sort_values('fecha')
    plt.figure(figsize=(10, 5))
    for turno in df_sorted['turno'].unique():
        df_turno = df_sorted[df_sorted['turno'] == turno]
        plt.plot(df_turno['fecha'].dt.strftime("%d-%m"), df_turno['OEE']*100,
                marker='o', label=f"Turno {turno}")

    plt.title("Evolución del OEE", fontsize=14)
    plt.ylabel("OEE (%)")
    plt.xlabel("Fecha")
    plt.legend()
    plt.axhline(y=85, color='green', linestyle='--', alpha=0.7, label='Excelente (85%)')
    plt.axhline(y=65, color='orange', linestyle='--', alpha=0.7, label='Aceptable (65%)')
    plt.xticks(rotation=45)

    img_evo = io.BytesIO()
    plt.savefig(img_evo, format="png", bbox_inches="tight")
    img_evo.seek(0)
    plot_evolucion = base64.b64encode(img_evo.getvalue()).decode()
    plt.close()

    # Pasar tabla y gráficos al template
    return render_template("oee.html",
                         tabla_oee=df.to_dict("records"),
                         plot_url=plot_url,
                         plot_disponibilidad=plot_disponibilidad,
                         plot_rendimiento=plot_rendimiento,
                         plot_calidad=plot_calidad,
                         plot_evolucion=plot_evolucion,
                         disponibilidad_promedio=disponibilidad_promedio,
                         rendimiento_promedio=rendimiento_promedio,
                         calidad_promedio=calidad_promedio,
                         oee_promedio=oee_promedio)

if __name__== '__main__':
    app.run(port=int(os.environ.get("FLASK_PORT", 5000)))