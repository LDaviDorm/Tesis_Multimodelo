"""Reparación de guardado V2. Ejecutar en el kernel existente, sin cambiar la libreta."""
from pathlib import Path as _Path
from datetime import datetime as _DateTime, timezone as _Timezone
import gc as _gc
import hashlib as _hashlib
import json as _json
import os as _os
import sys as _sys
import tempfile as _tempfile
import time as _time
import traceback as _traceback
import numpy as _np

_PAR_VERSION = "GUARDADO_WINDOWS_V1"
_PAR_CHECKPOINT = "076098b032528f1756977aae0f67ae5337eeeb564dea424a1482c7e7dbb2f7ac"


def _par_firma(obj):
    return _hashlib.sha256(_json.dumps(obj, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _par_leer_bytes(path):
    for intento in range(12):
        try:
            return _Path(path).read_bytes()
        except PermissionError:
            if intento == 11:
                raise
            _time.sleep(min(0.1 * 2 ** intento, 2.0))


def guardar(p, x):
    """Temporal único y cerrado; reintentos sin borrar antes el archivo de destino."""
    p = _Path(p)
    datos = _json.dumps(x, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
    with _tempfile.NamedTemporaryFile(mode="wb", prefix=".guardado_", suffix=".tmp",
                                     dir=str(p.parent), delete=False) as f:
        temporal = _Path(f.name)
        f.write(datos)
        f.flush()
        _os.fsync(f.fileno())
    for intento in range(12):
        try:
            _os.replace(temporal, p)
            return
        except PermissionError as error:
            if intento == 11:
                raise PermissionError(
                    f"No se pudo reemplazar {p}. No se borró el destino. "
                    f"La copia nueva permanece en {temporal}. "
                    "No reanudes todavía; conserva ambos archivos."
                ) from error
            _time.sleep(min(0.1 * 2 ** intento, 2.0))


def _par_validar_estado(st, matriz, esperado, nombre):
    if not isinstance(st, dict) or st.get("condicion") != esperado:
        raise ValueError(f"Condición incompatible: {nombre}")
    n = st.get("completados")
    if type(n) is not int or not 0 <= n <= len(matriz):
        raise ValueError(f"Contador inválido: {nombre}")
    bloques = st.get("bloques")
    if not isinstance(bloques, list):
        raise ValueError(f"Faltan bloques: {nombre}")
    pos = 0
    for b in bloques:
        ini, fin = b.get("inicio"), b.get("fin")
        if type(ini) is not int or type(fin) is not int or ini != pos or not ini < fin <= n:
            raise ValueError(f"Bloques no consecutivos: {nombre}")
        trozo = _np.asarray(matriz[ini:fin])
        h = _hashlib.sha256(trozo.tobytes()).hexdigest()
        if not _np.isfinite(trozo).all() or h != b.get("sha256"):
            raise ValueError(f"No coincide el vector guardado en {nombre}, bloque {ini}:{fin}")
        pos = fin
    if pos != n:
        raise ValueError(f"Contador y bloques no coinciden: {nombre}")
    return n


def _par_validar_resultados(r, protocolo):
    if not isinstance(r, dict) or r.get("firma_protocolo") != protocolo:
        raise ValueError("El resultado general pertenece a otro protocolo.")
    if _par_firma(r["protocolo"]) != protocolo:
        raise ValueError("Firma del protocolo general incorrecta.")
    for clave, registro in r.get("modelos", {}).items():
        for tarea, run in registro.get("tareas", {}).items():
            if _par_firma(run["datos"]) != run.get("firma"):
                raise ValueError(f"Firma de resultado incorrecta: {clave}/{tarea}")


def reparar_guardado_actual(ns):
    ns["GUARDADO_REPARADO"] = False
    necesarios = ["BASE", "CACHE", "SALIDA", "R", "FIRMA_PROTOCOLO", "MODELOS", "TAREAS", "ENTORNO"]
    faltan = [k for k in necesarios if k not in ns]
    if faltan:
        raise RuntimeError("Falta el estado del kernel: " + ", ".join(faltan) +
                           ". No ejecutes la inferencia ni borres la caché.")
    base, cache, salida = map(_Path, (ns["BASE"], ns["CACHE"], ns["SALIDA"]))
    r, protocolo = ns["R"], ns["FIRMA_PROTOCOLO"]
    _par_validar_resultados(r, protocolo)
    cfg = ns["MODELOS"]["nemotron3_1b"]
    tarea = ns["TAREAS"]["miracl_es_hn"]
    docs = tarea["docs"]
    esperado = dict(modelo=cfg, tipo="document", prefijo=cfg["document"],
        entradas=_par_firma(list(docs.items())), entorno=ns["ENTORNO"], protocolo=protocolo)
    if _par_firma(esperado) != _PAR_CHECKPOINT:
        raise ValueError("El punto de control calculado no coincide con el del error. No se modificó nada.")
    carpeta = cache / "vectores" / "nemotron3_1b"
    destino = carpeta / (_PAR_CHECKPOINT + ".json")
    pendiente = carpeta / (_PAR_CHECKPOINT + ".json.tmp")
    ruta_npy = carpeta / (_PAR_CHECKPOINT + ".npy")
    if not destino.is_file() or not ruta_npy.is_file():
        raise FileNotFoundError("No están el JSON confirmado y su NPY. No se creará una matriz nueva.")

    # Respaldos pequeños; la matriz NPY se abre solo para lectura.
    sello = _DateTime.now(_Timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    respaldo = cache / "_respaldo_guardado" / sello
    respaldo.mkdir(parents=True, exist_ok=False)
    originales = {}
    rutas = [destino, pendiente, salida, _Path(str(salida) + ".tmp"), cache / "protocolo_v2.json"]
    for p in rutas:
        if p.is_file():
            b = _par_leer_bytes(p)
            originales[str(p)] = b
            with (respaldo / p.name).open("xb") as f:
                f.write(b); f.flush(); _os.fsync(f.fileno())
    guardar(respaldo / "resultado_en_memoria.json", r)
    print("Respaldo creado:", respaldo, flush=True)

    actual = _json.loads(originales[str(destino)])
    nuevo = _json.loads(originales[str(pendiente)]) if str(pendiente) in originales else None
    matriz = _np.load(ruta_npy, mmap_mode="r", allow_pickle=False)
    try:
        if matriz.shape != (len(docs), cfg["dim"]) or matriz.dtype != _np.float32:
            raise ValueError("La matriz NPY tiene forma o tipo incorrectos.")
        antes = _par_validar_estado(actual, matriz, esperado, destino.name)
        despues, elegido = antes, actual
        if nuevo is not None:
            candidatos = _par_validar_estado(nuevo, matriz, esperado, pendiente.name)
            menor, mayor = (actual, nuevo) if antes <= candidatos else (nuevo, actual)
            if mayor["bloques"][:len(menor["bloques"])] != menor["bloques"]:
                raise ValueError("El temporal no es una continuación del estado confirmado.")
            if candidatos > antes:
                despues, elegido = candidatos, nuevo
    finally:
        matriz._mmap.close()
        del matriz

    # Detener si otro escritor cambió el checkpoint mientras se revisaba.
    if _par_leer_bytes(destino) != originales[str(destino)]:
        raise RuntimeError("Otro proceso modificó el checkpoint. Detén la otra ejecución antes de seguir.")
    if nuevo is not None and _par_leer_bytes(pendiente) != originales[str(pendiente)]:
        raise RuntimeError("Otro proceso modificó el temporal. No se reemplazó el checkpoint.")
    if despues > antes:
        guardar(destino, elegido)
    if _json.loads(_par_leer_bytes(destino)) != elegido:
        raise RuntimeError("No se confirmó el checkpoint reparado.")

    r_disco = _json.loads(_par_leer_bytes(salida)) if salida.is_file() else None
    if r_disco is not None:
        _par_validar_resultados(r_disco, protocolo)
        for clave, registro in r_disco.get("modelos", {}).items():
            for tarea_nombre, run in registro.get("tareas", {}).items():
                en_memoria = r.get("modelos", {}).get(clave, {}).get("tareas", {}).get(tarea_nombre)
                if en_memoria != run:
                    raise RuntimeError("El resultado en disco y el kernel difieren; no se sobrescribirá el resultado.")
    archivo_parche = base / "reparar_guardado_benchmark.py"
    auditoria = dict(version=_PAR_VERSION, fecha_utc=_DateTime.now(_Timezone.utc).isoformat(),
        script_sha256=_hashlib.sha256(_par_leer_bytes(archivo_parche)).hexdigest(),
        alcance="Solo persistencia con reintentos; sin cambios en modelos, vectores, datos o métricas",
        protocolo_original=protocolo, checkpoint=destino.name,
        completados_antes=antes, completados_despues=despues,
        respaldo=str(respaldo.relative_to(base)), temporal_original_conservado=pendiente.is_file())
    r.setdefault("mantenimiento_guardado", []).append(auditoria)
    ns["guardar"] = guardar
    guardar(salida, r)
    guardar(respaldo / "auditoria_reparacion.json", auditoria)

    # Liberar referencias retenidas por el error, no resultados ni variables del experimento.
    tb = getattr(_sys, "last_traceback", None)
    if tb is not None:
        cursor = tb
        while cursor is not None:
            if cursor.tb_frame.f_code.co_name in ("vectores_cache", "encode_controlado", "guardar"):
                try:
                    cursor.tb_frame.clear()
                except RuntimeError:
                    pass
            cursor = cursor.tb_next
        del cursor, tb
    for atributo in ("last_traceback", "last_value", "last_type", "last_exc"):
        if hasattr(_sys, atributo):
            setattr(_sys, atributo, None)
    _gc.collect()
    ns["GUARDADO_REPARADO"] = True
    print(f"Nemotron / MIRACL: {antes} -> {despues} documentos confirmados.", flush=True)
    for clave, registro in r.get("modelos", {}).items():
        print(clave, "| tareas completas:", ", ".join(registro.get("tareas", {})), flush=True)
    print("GUARDADO REPARADO. Elimina la celda temporal y repite solo la celda de ejecución de modelos (5).")
    print("No ejecutes todas las celdas. No se modificó el protocolo ni la libreta original.")


if not globals().get("_PAR_SOLO_TEST", False):
    reparar_guardado_actual(globals())
