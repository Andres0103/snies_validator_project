
export type ValidationStatus =
  | 'PENDIENTE'
  | 'PROCESANDO'
  | 'COMPLETADO'
  | 'COMPLETADO_CON_OBSERVACIONES'
  | 'COMPLETADO_PARCIAL'
  | 'FALLIDO';

export interface RejectedFile {
  nombre_archivo: string;
  motivo: string;
}

export interface ValidationFileSummary {
  nombre_archivo: string;
  estado: string;
  archivo_marcado: string | null;
  total_errores: number;
  total_advertencias: number;
}

export interface ValidationResponse {
  id: string;
  estado: ValidationStatus;
  progreso: number;
  mensaje: string;
  creado_en: string;
  iniciado_en: string | null;
  finalizado_en: string | null;
  total_archivos: number;
  total_archivos_validos: number;
  total_archivos_procesados: number;
  total_archivos_fallidos: number;
  total_errores: number;
  total_advertencias: number;
  archivos: ValidationFileSummary[];
  archivos_rechazados: RejectedFile[];
}

export interface ValidationIssue {
  nombre_archivo: string;
  hoja: string;
  fila: number;
  columna: string;
  valor: string | null;
  mensaje: string;
  severidad: string;
}

export interface ValidationErrorsResponse {
  items: ValidationIssue[];
}

export interface ValidationHistoryResponse {
  items: ValidationResponse[];
}
