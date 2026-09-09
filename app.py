import streamlit as st
import pandas as pd
import io
import re
from datetime import datetime

st.set_page_config(page_title="Sistema de Auditoría y Control", layout="wide")

st.title("📊 Sistema de Control y Auditoría de Documentos")
st.write("Sube la planilla CSV, el archivo TXT y selecciona los archivos de las carpetas de respaldos.")

# --- 1. SECCIÓN DE CARGA DE ARCHIVOS ---
st.subheader("1. Carga de Planilla y TXT")

col1, col2 = st.columns(2)
with col1:
    archivo_csv = st.file_uploader("Cargar planilla CSV", type=["csv"])
with col2:
    archivo_txt = st.file_uploader("Cargar archivo TXT", type=["txt"])

st.markdown("---")
st.subheader("2. Carga de Respaldos (Seleccionar todos los archivos con Ctrl+A)")

col3, col4, col5 = st.columns(3)
with col3:
    archivos_cedulas = st.file_uploader(
        "Archivos de Cédulas", 
        accept_multiple_files=True,
        help="Entrá a la carpeta de cédulas, presioná Ctrl+A y subilos todos."
    )
with col4:
    archivos_autorizaciones = st.file_uploader(
        "Archivos de Autorizaciones", 
        accept_multiple_files=True,
        help="Entrá a la carpeta de autorizaciones, presioná Ctrl+A y subilos todos."
    )
with col5:
    archivos_documentos = st.file_uploader(
        "Archivos de Documentos Varios", 
        accept_multiple_files=True,
        help="Entrá a la carpeta de documentos, presioná Ctrl+A y subilos todos."
    )

st.markdown("---")

# --- 2. BOTÓN DE PROCESAMIENTO ---
if st.button("🚀 Procesar Auditoría Completa", use_container_width=True):
    if not archivo_csv or not archivo_txt:
        st.warning("⚠️ Debes cargar la planilla CSV y el archivo TXT para realizar la validación.")
    else:
        try:
            # --- LECTURA CSV Y TXT ---
            df_csv = pd.read_csv(archivo_csv, sep=';', encoding='latin-1')
            df_csv.columns = [c.strip() for c in df_csv.columns]
            
            col_cedula_csv = 'N° de cédula de identidad del Beneficiario'
            col_monto_csv = 'Monto por descontarse en el mes'
            
            df_csv[col_monto_csv] = pd.to_numeric(
                df_csv[col_monto_csv].astype(str).str.strip(), errors='coerce'
            ).fillna(0)
            
            entidad_cod = df_csv['Código de Cooperativa o Entidad'].iloc[0] if 'Código de Cooperativa o Entidad' in df_csv.columns else 96

            # Lectura TXT (Referencia para Cédulas)
            cedulas_txt = set()
            lineas_txt = archivo_txt.getvalue().decode('latin-1').splitlines()
            for linea in lineas_txt:
                partes = linea.split()
                if len(partes) >= 2:
                    try:
                        cedulas_txt.add(str(int(partes[1])))
                    except ValueError:
                        pass

            # --- ANÁLISIS DE CÉDULAS ---
            nombres_cedulas_cargadas = [f.name for f in (archivos_cedulas or [])]
            cedulas_encontradas_drive = set()
            
            for nombre_f in nombres_cedulas_cargadas:
                numeros = re.findall(r'\d+', nombre_f)
                for num in numeros:
                    cedulas_encontradas_drive.add(num)

            cedulas_faltantes_list = []
            for c in cedulas_txt:
                if c not in cedulas_encontradas_drive:
                    cedulas_faltantes_list.append({
                        'Entidad': entidad_cod,
                        'Tipo de diferencia': 'FALTANTE',
                        'C.I.': c
                    })
            df_faltantes_cedulas = pd.DataFrame(cedulas_faltantes_list)

            # --- ANÁLISIS DE AUTORIZACIONES Y DOCUMENTOS VARIOS ---
            conteo_esperado = df_csv.groupby(col_cedula_csv).size().to_dict()
            
            nombres_aut = [f.name for f in (archivos_autorizaciones or [])]
            nombres_doc = [f.name for f in (archivos_documentos or [])]

            conteo_aut_encontrado = {}
            for name in nombres_aut:
                nums = re.findall(r'\d+', name)
                for n in nums:
                    conteo_aut_encontrado[n] = conteo_aut_encontrado.get(n, 0) + 1

            conteo_doc_encontrado = {}
            for name in nombres_doc:
                nums = re.findall(r'\d+', name)
                for n in nums:
                    conteo_doc_encontrado[n] = conteo_doc_encontrado.get(n, 0) + 1

            doc_oblig_list = []
            cedulas_unicas_csv = set(str(int(c)) for c in df_csv[col_cedula_csv].dropna().unique())

            for ci in cedulas_unicas_csv:
                esperados = conteo_esperado.get(int(ci), 0)
                encontrados_doc = conteo_doc_encontrado.get(ci, 0)
                
                if encontrados_doc < esperados:
                    doc_oblig_list.append({
                        'Entidad': entidad_cod,
                        'Tipo de diferencia': 'FALTANTE',
                        'C.I.': ci,
                        'C.I. reconocida en Drive': ci if encontrados_doc > 0 else None,
                        'Nivel de control': 'C.I. + CANTIDAD',
                        'Declarados en planilla': esperados,
                        'Encontrados': encontrados_doc,
                        'Cantidad faltante/adicional': esperados - encontrados_doc,
                        'Nota': 'Comparación exclusiva por cantidad de apariciones de la C.I.; el número de operación se ignora.'
                    })
                elif encontrados_doc > esperados:
                    doc_oblig_list.append({
                        'Entidad': entidad_cod,
                        'Tipo de diferencia': 'ADICIONAL',
                        'C.I.': ci,
                        'C.I. reconocida en Drive': ci,
                        'Nivel de control': 'C.I. + CANTIDAD',
                        'Declarados en planilla': esperados,
                        'Encontrados': encontrados_doc,
                        'Cantidad faltante/adicional': encontrados_doc - esperados,
                        'Nota': 'Comparación exclusiva por cantidad de apariciones de la C.I.; el número de operación se ignora.'
                    })

            df_faltantes_doc_oblig = pd.DataFrame(doc_oblig_list)

            # --- CONSTRUCCIÓN DE INFORME EJECUTIVO ---
            total_registros_csv = len(df_csv)
            ci_unicas_oficiales = len(cedulas_unicas_csv)
            ci_faltantes_cnt = len(df_faltantes_cedulas)
            
            informe_ejecutivo = pd.DataFrame([{
                'Entidad': entidad_cod,
                'Registros planilla': total_registros_csv,
                'C.I. únicas oficiales': ci_unicas_oficiales,
                'Archivos de cédula encontrados': len(nombres_cedulas_cargadas),
                'C.I. únicas reales encontradas': len(cedulas_encontradas_drive),
                'C.I. faltantes': ci_faltantes_cnt,
                'C.I. adicionales': 0,
                'Cédulas repetidas (C.I.)': 0,
                'Archivos adicionales por repetición': 0,
                'Autorizaciones esperadas': total_registros_csv,
                'Autorizaciones encontradas': len(nombres_aut),
                'Autorizaciones faltantes': max(0, total_registros_csv - len(nombres_aut)),
                'Autorizaciones adicionales': max(0, len(nombres_aut) - total_registros_csv),
                'Obligaciones/Documentos esperados': total_registros_csv,
                'Obligaciones/Documentos encontrados': len(nombres_doc),
                'Obligaciones/Documentos faltantes': sum(d['Cantidad faltante/adicional'] for d in doc_oblig_list if d['Tipo de diferencia'] == 'FALTANTE'),
                'Obligaciones/Documentos adicionales': sum(d['Cantidad faltante/adicional'] for d in doc_oblig_list if d['Tipo de diferencia'] == 'ADICIONAL'),
                'Conciliados por nombre único': 0,
                'Archivos sin identificar': 0,
                'Casos REVISAR': ci_faltantes_cnt + len(df_faltantes_doc_oblig),
                'Estado general': 'REVISAR' if (ci_faltantes_cnt + len(df_faltantes_doc_oblig)) > 0 else 'CORRECTO'
            }])

            df_cedulas_repetidas = pd.DataFrame(columns=['Entidad', 'C.I.', 'Cantidad de archivos', 'Archivos adicionales por repetición', 'Archivos', 'Rutas / origen'])

            # --- RESULTADOS EN PANTALLA ---
            st.success("¡Procesamiento finalizado con éxito!")
            
            st.subheader("📌 Resumen del Informe Ejecutivo")
            st.dataframe(informe_ejecutivo, use_container_width=True)

            if not df_faltantes_cedulas.empty:
                st.subheader("⚠️ Cédulas Faltantes")
                st.dataframe(df_faltantes_cedulas, use_container_width=True)

            if not df_faltantes_doc_oblig.empty:
                st.subheader("⚠️ Faltantes y Adicionales en Documentos / Obligaciones")
                st.dataframe(df_faltantes_doc_oblig, use_container_width=True)

            # --- GENERACIÓN DEL EXCEL CON NOMBRE DINÁMICO ---
            fecha_actual = datetime.now().strftime("%d-%m-%Y")
            nombre_archivo_excel = f"control descuento Hacienda {fecha_actual}.xlsx"

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                informe_ejecutivo.to_excel(writer, sheet_name='Informe Ejecutivo', index=False)
                df_cedulas_repetidas.to_excel(writer, sheet_name='Cédulas repetidas', index=False)
                df_faltantes_cedulas.to_excel(writer, sheet_name='Faltantes Adic Cédulas', index=False)
                df_faltantes_doc_oblig.to_excel(writer, sheet_name='Faltantes Adic Doc Oblig', index=False)

            st.download_button(
                label=f"📥 Descargar {nombre_archivo_excel}",
                data=output.getvalue(),
                file_name=nombre_archivo_excel,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        except Exception as e:
            st.error(f"Ocurrió un error durante la auditoría: {e}")
