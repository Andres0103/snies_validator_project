import { Component, OnInit, inject, ChangeDetectorRef } from '@angular/core';

import { ActivatedRoute } from '@angular/router';

import { ValidationHistoryService } from '../../core/services/validation-history.service';

import {
  LocalValidationRecord,
  StoredValidationFile,
} from '../../core/models/validation-history.model';

import { ValidationIssue } from '../../core/models/validation.model';

@Component({
  selector: 'app-history',
  standalone: true,
  imports: [],
  templateUrl: './history.html',
  styleUrl: './history.scss',
})
export class History implements OnInit {
  // =========================================================
  // SERVICIOS
  // =========================================================

  // Servicio encargado de administrar los registros en IndexedDB.
  private historyService = inject(ValidationHistoryService);

  // Permite actualizar manualmente la vista de Angular cuando sea necesario.
  private cdr = inject(ChangeDetectorRef);

  // Permite recuperar el identificador enviado desde Dashboard.
  private route = inject(ActivatedRoute);

  // =========================================================
  // PROPIEDADES DEL HISTORIAL
  // =========================================================

  // Lista completa de validaciones recuperadas de IndexedDB.
  validations: LocalValidationRecord[] = [];

  // Registro que el usuario está consultando actualmente.
  selectedValidation: LocalValidationRecord | null = null;

  // Incidencias del registro seleccionado.
  issues: ValidationIssue[] = [];

  // Fecha seleccionada en el buscador.
  // Formato: YYYY-MM-DD.
  searchDate = '';

  // =========================================================
  // ESTADOS DE LA INTERFAZ
  // =========================================================

  // Indica si se está consultando el historial.
  isLoading = false;

  // Se conserva para controlar el estado de carga de las incidencias.
  isLoadingIssues = false;

  // Mensaje de error que se muestra en pantalla.
  errorMessage = '';

  // =========================================================
  // INICIALIZACIÓN
  // =========================================================

  /**
   * Se ejecuta cuando Angular inicializa el componente.
   *
   * Recuperamos automáticamente las validaciones almacenadas
   * localmente en IndexedDB.
   */
  ngOnInit(): void {
    void this.loadHistory();
  }

  // =========================================================
  // BÚSQUEDA Y FILTRADO
  // =========================================================

  /**
   * Devuelve las validaciones que coinciden con la fecha seleccionada.
   *
   * Si no hay una fecha seleccionada, devuelve todos los registros.
   *
   * Utilizamos savedAt porque representa la fecha en la que
   * se almacenó localmente la validación.
   */
  get filteredValidations(): LocalValidationRecord[] {
    // Sin fecha seleccionada, mostramos todo el historial.
    if (!this.searchDate) {
      return this.validations;
    }

    return this.validations.filter((validation) => {
      const date = new Date(validation.savedAt);

      // Ignoramos registros que tengan una fecha inválida.
      if (Number.isNaN(date.getTime())) {
        return false;
      }

      // Construimos la fecha utilizando el horario local.
      const year = date.getFullYear();

      const month = String(date.getMonth() + 1).padStart(2, '0');

      const day = String(date.getDate()).padStart(2, '0');

      const recordDate = `${year}-${month}-${day}`;

      // Comparamos la fecha del registro con la seleccionada.
      return recordDate === this.searchDate;
    });
  }

  /**
   * Actualiza la fecha del buscador.
   *
   * Se ejecuta cuando el usuario modifica el selector de fecha.
   */
  onDateChange(event: Event): void {
    const input = event.target as HTMLInputElement;

    this.searchDate = input.value;
  }

  /**
   * Limpia el filtro de fecha.
   *
   * Después de ejecutar este método, se muestran nuevamente
   * todas las validaciones.
   */
  clearDateFilter(): void {
    this.searchDate = '';
  }

  // =========================================================
  // CONSULTA DEL HISTORIAL
  // =========================================================

  /**
   * Recupera todas las validaciones almacenadas en IndexedDB.
   *
   * Importante:
   * Este método no consulta el backend.
   */
  async loadHistory(): Promise<void> {
    this.isLoading = true;

    this.errorMessage = '';

    // Actualizamos la vista para mostrar el indicador de carga.
    this.cdr.detectChanges();

    try {
      // Recuperamos todos los registros almacenados localmente.
      this.validations = await this.historyService.getAll();

      // Recuperamos el identificador enviado mediante la URL.
      const selectedId = this.route.snapshot.queryParamMap.get('id');

      // Si llegamos desde una actividad reciente,
      // seleccionamos automáticamente su validación.
      if (selectedId) {
        const requestedValidation = this.validations.find(
          (validation) => validation.id === selectedId,
        );

        if (requestedValidation) {
          // Abrimos automáticamente el detalle.
          this.viewDetails(requestedValidation);

          console.log('[HISTORY] Validación abierta desde Dashboard:', selectedId);
        } else {
          console.warn('[HISTORY] No se encontró la validación solicitada:', selectedId);
        }
      }

      console.log('[HISTORY] Registros recuperados de IndexedDB:', this.validations.length);

      // Si hay un registro seleccionado, actualizamos sus datos.
      if (this.selectedValidation) {
        const updatedRecord = this.validations.find(
          (item) => item.id === this.selectedValidation?.id,
        );

        this.selectedValidation = updatedRecord ?? null;

        this.issues = updatedRecord?.issues ?? [];
      }
    } catch (error) {
      console.error('[HISTORY] Error consultando IndexedDB:', error);

      this.errorMessage = 'No fue posible recuperar el historial almacenado en este navegador.';
    } finally {
      // La consulta terminó, independientemente del resultado.
      this.isLoading = false;

      // Actualizamos la interfaz con los datos recuperados.
      this.cdr.detectChanges();
    }
  }

  // =========================================================
  // CONSULTA DE DETALLES
  // =========================================================

  /**
   * Muestra el detalle de una validación.
   *
   * Las incidencias ya están almacenadas dentro del registro,
   * por lo que no necesitamos consultarlas nuevamente al backend.
   */
  viewDetails(validation: LocalValidationRecord): void {
    // Guardamos el registro seleccionado.
    this.selectedValidation = validation;

    // Recuperamos las incidencias almacenadas.
    this.issues = validation.issues ?? [];

    // No necesitamos una consulta adicional.
    this.isLoadingIssues = false;

    // Limpiamos mensajes anteriores.
    this.errorMessage = '';

    console.log('[HISTORY] Detalle consultado:', validation.id);
  }

  /**
   * Cierra el panel de detalle.
   */
  closeDetails(): void {
    this.selectedValidation = null;

    this.issues = [];

    this.isLoadingIssues = false;
  }

  // =========================================================
  // DESCARGA DE ARCHIVOS
  // =========================================================

  /**
   * Descarga el reporte consolidado almacenado localmente.
   */
  downloadReport(validation: LocalValidationRecord): void {
    if (!validation.report?.blob) {
      this.errorMessage = 'Esta validación no tiene un reporte consolidado almacenado.';

      return;
    }

    this.downloadStoredFile(validation.report, `reporte_validacion_${validation.id}.xlsx`);
  }

  /**
   * Descarga un archivo Excel marcado almacenado localmente.
   *
   * Buscamos el archivo por su nombre dentro de generatedFiles.
   */
  downloadMarkedFile(validation: LocalValidationRecord, filename: string): void {
    const file = validation.generatedFiles?.find((item) => item.name === filename);

    if (!file) {
      this.errorMessage = `No se encontró el archivo marcado: ${filename}`;

      return;
    }

    this.downloadStoredFile(file, file.name);
  }

  /**
   * Descarga el archivo original que el usuario cargó.
   *
   * Buscamos el archivo dentro de originalFiles.
   */
  downloadOriginalFile(validation: LocalValidationRecord, filename: string): void {
    const file = validation.originalFiles?.find((item) => item.name === filename);

    if (!file) {
      this.errorMessage = `No se encontró el archivo original: ${filename}`;

      return;
    }

    this.downloadStoredFile(file, file.name);
  }

  /**
   * Método reutilizable para descargar cualquier archivo almacenado.
   *
   * Recibe un Blob y crea una URL temporal que permite al navegador
   * descargarlo sin necesidad de consultar el backend.
   */
  private downloadStoredFile(file: StoredValidationFile, filename: string): void {
    try {
      // Creamos una URL temporal a partir del Blob.
      const url = window.URL.createObjectURL(file.blob);

      // Creamos un enlace de descarga.
      const link = document.createElement('a');

      link.href = url;

      link.download = filename;

      // Lo agregamos temporalmente al documento.
      document.body.appendChild(link);

      // Iniciamos la descarga.
      link.click();

      // Eliminamos el enlace.
      link.remove();

      // Liberamos la URL temporal después de iniciar la descarga.
      window.setTimeout(() => {
        window.URL.revokeObjectURL(url);
      }, 1000);
    } catch (error) {
      console.error('[HISTORY] Error descargando archivo:', error);

      this.errorMessage = 'No fue posible descargar el archivo almacenado.';
    }
  }

  // =========================================================
  // ELIMINACIÓN DE REGISTROS
  // =========================================================

  /**
   * Elimina una validación de IndexedDB.
   *
   * También elimina los archivos asociados porque están
   * almacenados dentro del mismo registro.
   */
  async deleteValidation(validation: LocalValidationRecord): Promise<void> {
    // Solicitamos confirmación antes de eliminar.
    const confirmed = window.confirm(
      `¿Deseas eliminar del historial la validación ${validation.id}? Esta acción también eliminará los archivos almacenados localmente.`,
    );

    if (!confirmed) {
      return;
    }

    this.errorMessage = '';

    try {
      // Eliminamos el registro de IndexedDB.
      await this.historyService.delete(validation.id);

      console.log('[HISTORY] Validación eliminada:', validation.id);

      // Si eliminamos el registro que estábamos consultando,
      // cerramos automáticamente su panel de detalle.
      if (this.selectedValidation?.id === validation.id) {
        this.closeDetails();
      }

      // Actualizamos la tabla después de eliminar.
      await this.loadHistory();
    } catch (error) {
      console.error('[HISTORY] Error eliminando validación:', error);

      this.errorMessage = 'No fue posible eliminar la validación del historial.';
    }
  }

  // =========================================================
  // FORMATO DE FECHAS
  // =========================================================

  /**
   * Convierte una fecha ISO en una fecha legible para el usuario.
   *
   * Ejemplo:
   * 2026-11-17T09:26:00 -> 17/11/2026, 9:26 a. m.
   */
  formatDate(value: string): string {
    if (!value) {
      return 'Fecha no disponible';
    }

    const date = new Date(value);

    // Comprobamos que la fecha sea válida.
    if (Number.isNaN(date.getTime())) {
      return 'Fecha no válida';
    }

    return date.toLocaleString('es-CO', {
      dateStyle: 'short',
      timeStyle: 'short',
    });
  }
}
