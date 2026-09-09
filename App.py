import streamlit as st
import pandas as pd

# Configuración de la página
st.set_page_config(page_title="Sistema de Validación", layout="wide")

st.title("📊 Sistema de Cruce y Validación de Documentos")
st.write("Sube los archivos correspondientes para realizar el cruce automático.")

# 1. BOTONES DE CARGA DE ARCHIVOS
col1, col2 = st.columns(2)

with col1:
    archivo_csv = st.file_uploader("1. Cargar archivo CSV", type=["csv"])

with col2:
    archivo_txt = st.file_uploader("2. Cargar archivo TXT", type=["txt"])

st.markdown("---")

# 2. BOTÓN PRINCIPAL DE CRUCE
if st.button("🚀 Cruzar Información", use_container_width=True):
    if archivo_csv is None or archivo_txt is None:
        st.warning("⚠️ Debes subir ambos archivos (CSV y TXT) antes de realizar el cruce.")
    else:
        try:
            # Procesar el CSV
            df_csv = pd.read_csv(archivo_csv, sep=';', encoding='latin-1')
            df_csv.columns = [col.strip() for col in df_csv.columns]
            
            col_cedula_csv = 'N° de cédula de identidad del Beneficiario'
            col_monto_csv = 'Monto por descontarse en el mes'
            col_nombre = 'Nombres y Apellidos del Beneficiario'
            
            df_csv[col_monto_csv] = pd.to_numeric(
                df_csv[col_monto_csv].astype(str).str.strip(), errors='coerce'
            ).fillna(0)
            
            # Sumar montos por cédula en CSV
            csv_resumen = df_csv.groupby([col_cedula_csv, col_nombre])[col_monto_csv].sum().reset_index()
            csv_resumen.rename(columns={col_monto_csv: 'Monto_Total_CSV'}, inplace=True)
            
            # Procesar el TXT
            registros_txt = []
            lineas = archivo_txt.getvalue().decode('latin-1').splitlines()
            for linea in lineas:
                partes = linea.split()
                if len(partes) >= 3:
                    registros_txt.append({
                        'Cedula': int(partes[1]),
                        'Monto_TXT': float(partes[2]),
                        'Num_Socio_TXT': partes[0]
                    })
            df_txt = pd.DataFrame(registros_txt)
            
            # Cruzar datos
            resultado = pd.merge(csv_resumen, df_txt, left_on=col_cedula_csv, right_on='Cedula', how='outer')
            resultado['Monto_Total_CSV'] = resultado['Monto_Total_CSV'].fillna(0)
            resultado['Monto_TXT'] = resultado['Monto_TXT'].fillna(0)
            resultado[col_nombre] = resultado[col_nombre].fillna('NO FIGURA EN CSV')
            resultado['Cedula_Final'] = resultado[col_cedula_csv].combine_first(resultado['Cedula'])
            resultado['Diferencia'] = resultado['Monto_Total_CSV'] - resultado['Monto_TXT']
            
            def determinar_estado(row):
                if row['Monto_Total_CSV'] == 0:
                    return '❌ Solo figura en TXT'
                elif row['Monto_TXT'] == 0:
                    return '❌ Solo figura en CSV'
                elif abs(row['Diferencia']) < 0.01:
                    return '✅ Correcto (Coincide)'
                else:
                    return '⚠️ Montos No Coinciden'
            
            resultado['Estado'] = resultado.apply(determinar_estado, axis=1)
            
            # Mostrar métricas rápidas
            st.success("¡Cruce de información completado exitosamente!")
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Registros", len(resultado))
            m2.metric("✅ Correctos", len(resultado[resultado['Estado'] == '✅ Correcto (Coincide)']))
            m3.metric("⚠️ Con Errores / Diferencias", len(resultado[resultado['Estado'] != '✅ Correcto (Coincide)']))
            
            # Tabla interactiva con los resultados
            st.subheader("📋 Resultado Detallado")
            
            columnas_visibles = [
                'Cedula_Final', col_nombre, 'Num_Socio_TXT', 
                'Monto_Total_CSV', 'Monto_TXT', 'Diferencia', 'Estado'
            ]
            
            df_mostrar = resultado[columnas_visibles].rename(columns={
                'Cedula_Final': 'Cédula',
                col_nombre: 'Beneficiario',
                'Num_Socio_TXT': 'N° Socio'
            })
            
            st.dataframe(df_mostrar, use_container_width=True)
            
        except Exception as e:
            st.error(f"Ocurrió un error al procesar los archivos: {e}")
