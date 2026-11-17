import { Component, OnInit, inject, ChangeDetectorRef } from '@angular/core';

import { RouterLink } from '@angular/router';

import { ValidationHistoryService } from '../../core/services/validation-history.service';

import { LocalValidationRecord } from '../../core/models/validation-history.model';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [RouterLink],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.scss',
})
export class Dashboard implements OnInit {
  // =========================================================
  // SERVICIOS
  // =========================================================

  // Servicio que recupera las validaciones guardadas en IndexedDB.
  private historyService = inject(ValidationHistoryService);

  // Permite actualizar la vista después de recuperar los registros.
  private cdr = inject(ChangeDetectorRef);

  // =========================================================
  // DATOS DEL DASHBOARD
  // =========================================================

  // Todas las validaciones almacenadas localmente.
  validations: LocalValidationRecord[] = [];

  // Cantidad de validaciones que se muestran inicialmente.
  visibleValidationsCount = 5;

  // Indica si se están cargando los datos.
  isLoading = false;

  // Mensaje de error para la interfaz.
  errorMessage = '';

  // =========================================================
  // INDICADORES
  // =========================================================

  /**
   * Cantidad total de procesos registrados.
   *
   * Incluye todas las validaciones guardadas,
   * independientemente de su estado.
   */
  get totalProcesses(): number {
    return this.validations.length;
  }

  /**
   * Cantidad de procesos completados correctamente.
   */
  get completedProcesses(): number {
    return this.validations.filter((validation) => validation.estado === 'COMPLETADO').length;
  }

  /**
   * Cantidad de procesos que requieren revisión.
   *
   * Incluye procesos completados con observaciones
   * y procesos completados parcialmente.
   */
  get processesWithObservations(): number {
    return this.validations.filter(
      (validation) =>
        validation.estado === 'COMPLETADO_CON_OBSERVACIONES' ||
        validation.estado === 'COMPLETADO_PARCIAL',
    ).length;
  }

  // =========================================================
  // ACTIVIDAD RECIENTE
  // =========================================================

  /**
   * Devuelve las últimas cinco validaciones.
   *
   * Se ordenan utilizando savedAt, que representa
   * la fecha en que cada registro fue guardado localmente.
   */

  /**
   * Devuelve las validaciones que deben mostrarse en el dashboard.
   *
   * Se ordenan desde la más reciente hasta la más antigua.
   * Inicialmente muestra cinco y permite ampliar la cantidad.
   */
  get recentValidations(): LocalValidationRecord[] {
    return [...this.validations]
      .sort((a, b) => {
        const dateA = new Date(a.savedAt).getTime();
        const dateB = new Date(b.savedAt).getTime();

        return dateB - dateA;
      })
      .slice(0, this.visibleValidationsCount);
  }

  /**
   * Indica si todavía existen validaciones por mostrar.
   */
  get hasMoreValidations(): boolean {
    return this.visibleValidationsCount < this.validations.length;
  }

  /**
   * Muestra cinco validaciones adicionales.
   */
  loadMoreValidations(): void {
    this.visibleValidationsCount = Math.min(
      this.visibleValidationsCount + 5,
      this.validations.length,
    );

    console.log(
      '[DASHBOARD] Validaciones visibles:',
      this.recentValidations.length,
      'de',
      this.validations.length,
    );
  }

  // =========================================================
  // INICIALIZACIÓN
  // =========================================================

  /**
   * Se ejecuta cuando Angular inicializa el dashboard.
   *
   * Recuperamos los datos del historial local.
   */
  ngOnInit(): void {
    void this.loadDashboard();
  }

  // =========================================================
  // CARGA DE INFORMACIÓN
  // =========================================================

  /**
   * Recupera las validaciones desde IndexedDB.
   *
   * No realiza peticiones al backend.
   */
  async loadDashboard(): Promise<void> {
    this.isLoading = true;

    this.errorMessage = '';

    this.cdr.detectChanges();

    try {
      // Recuperamos los registros almacenados localmente.
      this.validations = await this.historyService.getAll();

      console.log('[DASHBOARD] Validaciones recuperadas:', this.validations.length);

      console.log('[DASHBOARD] Procesos completados:', this.completedProcesses);

      console.log('[DASHBOARD] Procesos con observaciones:', this.processesWithObservations);
    } catch (error) {
      console.error('[DASHBOARD] Error recuperando las validaciones:', error);

      this.errorMessage = 'No fue posible recuperar la información del panel principal.';
    } finally {
      this.isLoading = false;

      this.cdr.detectChanges();
    }
  }

  // =========================================================
  // FORMATO DE FECHAS
  // =========================================================

  /**
   * Convierte una fecha en un formato legible.
   */
  formatDate(value: string): string {
    if (!value) {
      return 'Fecha no disponible';
    }

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
      return 'Fecha no válida';
    }

    return date.toLocaleString('es-CO', {
      dateStyle: 'short',
      timeStyle: 'short',
    });
  }

  // =========================================================
  // FORMATO DE ESTADOS
  // =========================================================

  /**
   * Devuelve el texto que se mostrará para cada estado.
   */
  getStatusLabel(status: string): string {
    const labels: Record<string, string> = {
      PENDIENTE: 'Pendiente',
      PROCESANDO: 'Procesando',
      COMPLETADO: 'Completado',
      COMPLETADO_CON_OBSERVACIONES: 'Con observaciones',
      COMPLETADO_PARCIAL: 'Completado parcialmente',
      FALLIDO: 'Fallido',
    };

    return labels[status] ?? status;
  }
}
