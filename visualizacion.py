import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Para evitar problemas con hilos en Flask
from flask import Flask, render_template
import io
import base64
from datetime import datetime

# --- 1. Inicialización de la Aplicación Flask ---
app = Flask(__name__)

# --- 2. Carga de los Datasets en Memoria ---
# Para eficiencia, cargamos los CSV una sola vez cuando la app se inicia.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
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
@app.route('/')
def index():
    # Obtener datos OEE para mostrar en el dashboard
    df_oee = calcular_oee()

    if df_oee is not None and not df_oee.empty:
        # Calcular OEE promedio
        oee_promedio = df_oee['OEE'].mean() * 100

        # Calcular promedios de los componentes
        disponibilidad_promedio = df_oee['Disponibilidad'].mean()
        rendimiento_promedio = df_oee['Rendimiento'].mean()
        calidad_promedio = df_oee['Calidad'].mean()

        # Preparar gráfico OEE para el dashboard (más pequeño)
        plt.figure(figsize=(10, 5))
        # Tomar solo los últimos 5 registros para el dashboard
        df_recent = df_oee.tail(5)
        bars = plt.bar(df_recent["turno"] + " " + df_recent["fecha"].dt.strftime("%d-%m"),
                      df_recent["OEE"]*100,
                      color=["#2ecc71" if x >= 0.85 else "#f39c12" if x >= 0.65 else "#e74c3c" for x in df_recent["OEE"]])
        plt.title("OEE por Turno (Últimos 5 registros)", fontsize=14)
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
        oee_plot_url = base64.b64encode(img.getvalue()).decode()
        plt.close()

        # Preparar datos para la tabla (últimos 5 registros)
        oee_data = df_recent.to_dict('records')

        return render_template('index.html',
                              oee_value=oee_promedio,
                              disponibilidad_promedio=disponibilidad_promedio,
                              rendimiento_promedio=rendimiento_promedio,
                              calidad_promedio=calidad_promedio,
                              oee_plot_url=oee_plot_url,
                              oee_data=oee_data)
    else:
        # Si no hay datos OEE, mostrar valores por defecto
        return render_template('index.html',
                              oee_value=0,
                              disponibilidad_promedio=0,
                              rendimiento_promedio=0,
                              calidad_promedio=0,
                              oee_plot_url="",
                              oee_data=[])

@app.route('/desperdicios')
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

@app.route('/horarios')
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
@app.route('/inventario')
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
        # Cargar datasets ampliados
        tiempos = pd.read_csv(os.path.join(DATA_DIR, "tiempos_produccion.csv"), parse_dates=["fecha"], dayfirst=True)
        produccion = pd.read_csv(os.path.join(DATA_DIR, "produccion_velocidad.csv"), parse_dates=["fecha"], dayfirst=True)
        calidad = pd.read_csv(os.path.join(DATA_DIR, "calidad.csv"), parse_dates=["fecha"], dayfirst=True)

        # Merge por fecha y turno
        df = tiempos.merge(produccion, on=["fecha", "turno"]).merge(calidad, on=["fecha", "turno"])

        # Calcular métricas OEE
        df["Disponibilidad"] = df["tiempo_operativo_min"] / df["tiempo_planificado_min"]
        df["Rendimiento"] = df["unidades_producidas"] / (df["tiempo_operativo_min"] * df["velocidad_ideal_upm"])
        df["Calidad"] = (df["unidades_totales"] - df["unidades_defectuosas"]) / df["unidades_totales"]
        df["OEE"] = df["Disponibilidad"] * df["Rendimiento"] * df["Calidad"]

        # Calcular velocidad real si no existe en el dataset
        if 'velocidad_real_upm' not in df.columns:
            df['velocidad_real_upm'] = df['unidades_producidas'] / df['tiempo_operativo_min'] * 60

        # Calcular eficiencia de calidad
        df['tasa_defectos'] = df['unidades_defectuosas'] / df['unidades_totales'] * 100

        return df
    except Exception as e:
        print(f"Error al calcular OEE: {e}")
        return None

@app.route("/oee")
def mostrar_oee():
    df = calcular_oee()
    if df is None:
        return "No se pudo calcular OEE", 500

    # Calcular estadísticas adicionales
    disponibilidad_promedio = df["Disponibilidad"].mean()
    rendimiento_promedio = df["Rendimiento"].mean()
    calidad_promedio = df["Calidad"].mean()
    oee_promedio = df["OEE"].mean()

    # Calcular por turno
    stats_por_turno = df.groupby('turno').agg({
        'OEE': 'mean',
        'Disponibilidad': 'mean',
        'Rendimiento': 'mean',
        'Calidad': 'mean',
        'unidades_producidas': 'mean',
        'unidades_defectuosas': 'mean',
        'tiempo_parada_min': 'mean'
    }).reset_index()

    # Top 5 causas de parada
    if 'causa_parada' in df.columns:
        causas_parada = df['causa_parada'].value_counts().head(5).to_dict()
    else:
        causas_parada = {}

    # Top 5 tipos de defectos
    if 'tipo_defecto' in df.columns:
        tipos_defecto = df['tipo_defecto'].value_counts().head(5).to_dict()
    else:
        tipos_defecto = {}

    # Distribución por producto
    if 'producto' in df.columns:
        productos_stats = df.groupby('producto').agg({
            'OEE': 'mean',
            'unidades_producidas': 'sum',
            'unidades_defectuosas': 'sum'
        }).reset_index()
        productos_stats['tasa_defectos'] = (productos_stats['unidades_defectuosas'] / productos_stats['unidades_producidas'] * 100).round(2)
    else:
        productos_stats = pd.DataFrame()

    # Gráfico principal OEE
    plt.figure(figsize=(14, 7))
    bars = plt.bar(df["turno"] + " " + df["fecha"].dt.strftime("%d-%m"), df["OEE"]*100,
                   color=["#2ecc71" if x >= 0.85 else "#f39c12" if x >= 0.65 else "#e74c3c" for x in df["OEE"]])
    plt.title("Indicador OEE por Turno", fontsize=16, fontweight='bold')
    plt.ylabel("OEE (%)", fontweight='bold')
    plt.xlabel("Turno y Fecha", fontweight='bold')
    plt.axhline(y=85, color='green', linestyle='--', alpha=0.7, label='Excelente (85%)')
    plt.axhline(y=65, color='orange', linestyle='--', alpha=0.7, label='Aceptable (65%)')
    plt.legend()
    plt.xticks(rotation=45, ha='right')
    plt.grid(axis='y', alpha=0.3)

    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                 f"{height:.1f}%", ha="center", va="bottom", fontweight='bold')

    img = io.BytesIO()
    plt.savefig(img, format="png", bbox_inches="tight", dpi=100)
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode()
    plt.close()

    # Gráfico de Disponibilidad
    plt.figure(figsize=(12, 6))
    bars = plt.bar(df["turno"] + " " + df["fecha"].dt.strftime("%d-%m"), df["Disponibilidad"]*100, color="#3498db")
    plt.title("Disponibilidad por Turno", fontsize=14, fontweight='bold')
    plt.ylabel("Disponibilidad (%)", fontweight='bold')
    plt.xticks(rotation=45, ha='right')
    plt.grid(axis='y', alpha=0.3)

    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                 f"{height:.1f}%", ha="center", va="bottom", fontweight='bold')

    img_disp = io.BytesIO()
    plt.savefig(img_disp, format="png", bbox_inches="tight", dpi=100)
    img_disp.seek(0)
    plot_disponibilidad = base64.b64encode(img_disp.getvalue()).decode()
    plt.close()

    # Gráfico de Rendimiento
    plt.figure(figsize=(12, 6))
    bars = plt.bar(df["turno"] + " " + df["fecha"].dt.strftime("%d-%m"), df["Rendimiento"]*100, color="#27ae60")
    plt.title("Rendimiento por Turno", fontsize=14, fontweight='bold')
    plt.ylabel("Rendimiento (%)", fontweight='bold')
    plt.xticks(rotation=45, ha='right')
    plt.grid(axis='y', alpha=0.3)

    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                 f"{height:.1f}%", ha="center", va="bottom", fontweight='bold')

    img_rend = io.BytesIO()
    plt.savefig(img_rend, format="png", bbox_inches="tight", dpi=100)
    img_rend.seek(0)
    plot_rendimiento = base64.b64encode(img_rend.getvalue()).decode()
    plt.close()

    # Gráfico de Calidad
    plt.figure(figsize=(12, 6))
    bars = plt.bar(df["turno"] + " " + df["fecha"].dt.strftime("%d-%m"), df["Calidad"]*100, color="#f39c12")
    plt.title("Calidad por Turno", fontsize=14, fontweight='bold')
    plt.ylabel("Calidad (%)", fontweight='bold')
    plt.xticks(rotation=45, ha='right')
    plt.grid(axis='y', alpha=0.3)

    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                 f"{height:.1f}%", ha="center", va="bottom", fontweight='bold')

    img_cal = io.BytesIO()
    plt.savefig(img_cal, format="png", bbox_inches="tight", dpi=100)
    img_cal.seek(0)
    plot_calidad = base64.b64encode(img_cal.getvalue()).decode()
    plt.close()

    # Gráfico de Evolución del OEE
    df_sorted = df.sort_values('fecha')
    plt.figure(figsize=(12, 6))
    colors = {'Mañana': '#e74c3c', 'Tarde': '#3498db', 'Noche': '#2ecc71'}

    for turno in df_sorted['turno'].unique():
        df_turno = df_sorted[df_sorted['turno'] == turno]
        plt.plot(df_turno['fecha'].dt.strftime("%d-%m"), df_turno['OEE']*100,
                marker='o', label=f"Turno {turno}", linewidth=2, markersize=6, color=colors.get(turno, '#000'))

    plt.title("Evolución del OEE por Turno", fontsize=14, fontweight='bold')
    plt.ylabel("OEE (%)", fontweight='bold')
    plt.xlabel("Fecha", fontweight='bold')
    plt.legend()
    plt.axhline(y=85, color='green', linestyle='--', alpha=0.7, label='Excelente (85%)')
    plt.axhline(y=65, color='orange', linestyle='--', alpha=0.7, label='Aceptable (65%)')
    plt.xticks(rotation=45, ha='right')
    plt.grid(alpha=0.3)

    img_evo = io.BytesIO()
    plt.savefig(img_evo, format="png", bbox_inches="tight", dpi=100)
    img_evo.seek(0)
    plot_evolucion = base64.b64encode(img_evo.getvalue()).decode()
    plt.close()

    # Gráfico de causas de parada (si existen)
    if causas_parada:
        plt.figure(figsize=(10, 6))
        causas = list(causas_parada.keys())
        valores = list(causas_parada.values())

        bars = plt.barh(causas, valores, color=['#e74c3c', '#f39c12', '#3498db', '#2ecc71', '#9b59b6'])
        plt.title("Top 5 Causas de Parada", fontsize=14, fontweight='bold')
        plt.xlabel("Frecuencia", fontweight='bold')

        for bar in bars:
            width = bar.get_width()
            plt.text(width + 0.1, bar.get_y() + bar.get_height()/2,
                    f'{int(width)}', ha='left', va='center', fontweight='bold')

        plt.tight_layout()
        img_causas = io.BytesIO()
        plt.savefig(img_causas, format="png", bbox_inches="tight", dpi=100)
        img_causas.seek(0)
        plot_causas = base64.b64encode(img_causas.getvalue()).decode()
        plt.close()
    else:
        plot_causas = None

    # Gráfico de tipos de defectos (si existen)
    if tipos_defecto:
        plt.figure(figsize=(10, 6))
        defectos = list(tipos_defecto.keys())
        valores = list(tipos_defecto.values())

        bars = plt.barh(defectos, valores, color=['#e74c3c', '#f39c12', '#3498db', '#2ecc71', '#9b59b6'])
        plt.title("Top 5 Tipos de Defectos", fontsize=14, fontweight='bold')
        plt.xlabel("Frecuencia", fontweight='bold')

        for bar in bars:
            width = bar.get_width()
            plt.text(width + 0.1, bar.get_y() + bar.get_height()/2,
                    f'{int(width)}', ha='left', va='center', fontweight='bold')

        plt.tight_layout()
        img_defectos = io.BytesIO()
        plt.savefig(img_defectos, format="png", bbox_inches="tight", dpi=100)
        img_defectos.seek(0)
        plot_defectos = base64.b64encode(img_defectos.getvalue()).decode()
        plt.close()
    else:
        plot_defectos = None

    # Pasar todos los datos al template
    return render_template("oee.html",
                         tabla_oee=df.to_dict("records"),
                         stats_por_turno=stats_por_turno.to_dict("records"),
                         productos_stats=productos_stats.to_dict("records") if not productos_stats.empty else [],
                         causas_parada=causas_parada,
                         tipos_defecto=tipos_defecto,
                         plot_url=plot_url,
                         plot_disponibilidad=plot_disponibilidad,
                         plot_rendimiento=plot_rendimiento,
                         plot_calidad=plot_calidad,
                         plot_evolucion=plot_evolucion,
                         plot_causas=plot_causas,
                         plot_defectos=plot_defectos,
                         disponibilidad_promedio=disponibilidad_promedio,
                         rendimiento_promedio=rendimiento_promedio,
                         calidad_promedio=calidad_promedio,
                         oee_promedio=oee_promedio)

if __name__== '__main__':
    app.run(port=int(os.environ.get("FLASK_PORT", 5000)))