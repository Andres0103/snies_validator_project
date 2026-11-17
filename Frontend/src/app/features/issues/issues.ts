import { Component, OnInit, ChangeDetectorRef, inject } from '@angular/core';

import { FormsModule } from '@angular/forms';
import { DatePipe } from '@angular/common';
import { ActivatedRoute, Router } from '@angular/router';

import { ValidationHistoryService } from '../../core/services/validation-history.service';
import { LocalValidationRecord } from '../../core/models/validation-history.model';
import { ValidationIssue } from '../../core/models/validation.model';

@Component({
  selector: 'app-issues',
  standalone: true,
  imports: [FormsModule, DatePipe],
  templateUrl: './issues.html',
  styleUrl: './issues.scss',
})
export class Issues implements OnInit {
  // =========================================================
  // SERVICIOS
  // =========================================================

  private historyService = inject(ValidationHistoryService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private cdr = inject(ChangeDetectorRef);

  // =========================================================
  // VALIDACIÓN CONSULTADA
  // =========================================================

  validationId = '';

  validation: LocalValidationRecord | null = null;

  issues: ValidationIssue[] = [];

  // =========================================================
  // FILTROS
  // =========================================================

  issueSearch = '';
  issueSeverity = 'all';
  issueFile = '';
  issueColumn = '';

  // =========================================================
  // ESTADOS DE LA INTERFAZ
  // =========================================================

  isLoading = false;
  hasSearched = false;
  errorMessage = '';

  // =========================================================
  // INICIALIZACIÓN
  // =========================================================

  ngOnInit(): void {
    // Recuperamos el ID si llegamos desde el historial
    // o si el usuario abre directamente una URL con ?id=...
    const id = this.route.snapshot.queryParamMap.get('id');

    if (id) {
      this.validationId = id;
      void this.searchValidation();
    }
  }

  // =========================================================
  // CONSULTAR VALIDACIÓN
  // =========================================================

  async searchValidation(): Promise<void> {
    const id = this.validationId.trim();

    if (!id) {
      this.errorMessage = 'Ingresa el identificador de la validación.';
      return;
    }

    this.isLoading = true;
    this.hasSearched = true;
    this.errorMessage = '';

    // Limpiamos los resultados anteriores.
    this.validation = null;
    this.issues = [];
    this.clearIssueFilters();

    this.cdr.detectChanges();

    try {
      console.log('[ISSUES] Consultando validación en IndexedDB:', id);

      const record = await this.historyService.getById(id);

      if (!record) {
        this.errorMessage =
          'No se encontró una validación con ese identificador en el historial local.';

        console.warn('[ISSUES] No se encontró la validación:', id);

        return;
      }

      // Recuperamos las incidencias almacenadas.
      this.issues = record.issues ?? [];

      // Compatibilidad con registros anteriores a la incorporación
      // de issuesLoadedSuccessfully.
      const issuesLoaded = record.issuesLoadedSuccessfully ?? this.issues.length > 0;

      // Construimos el registro que utilizará la interfaz.
      this.validation = {
        ...record,
        issuesLoadedSuccessfully: issuesLoaded,
      };

      console.log(
        '[ISSUES] Validación recuperada:',
        record.id,
        'Incidencias:',
        this.issues.length,
        'Consulta exitosa:',
        record.issuesLoadedSuccessfully,
      );

      // Actualizamos explícitamente la vista.
      this.cdr.detectChanges();

      // Actualizamos la URL sin perder el registro recuperado
      // si ocurre algún problema durante la navegación.
      void this.updateUrl(record.id);
    } catch (error) {
      console.error('[ISSUES] Error consultando validación:', error);

      this.errorMessage = 'No fue posible consultar el registro almacenado localmente.';

      this.validation = null;
      this.issues = [];
    } finally {
      // La carga debe finalizar tanto si la consulta
      // fue exitosa como si hubo un error.
      this.isLoading = false;

      console.log('[ISSUES] Consulta finalizada. isLoading:', this.isLoading);

      // Forzamos la actualización de la interfaz.
      this.cdr.detectChanges();
    }
  }

  // =========================================================
  // ACTUALIZAR URL
  // =========================================================

  private async updateUrl(id: string): Promise<void> {
    try {
      await this.router.navigate([], {
        relativeTo: this.route,
        queryParams: { id },
        queryParamsHandling: 'merge',
        replaceUrl: true,
      });
    } catch (error) {
      console.warn('[ISSUES] No fue posible actualizar la URL:', error);
    }
  }

  // =========================================================
  // FILTROS DISPONIBLES
  // =========================================================

  get issueFiles(): string[] {
    return [...new Set(this.issues.map((issue) => issue.nombre_archivo))].sort();
  }

  get issueColumns(): string[] {
    return [...new Set(this.issues.map((issue) => issue.columna))].sort();
  }

  // =========================================================
  // CLASIFICACIÓN DE SEVERIDAD
  // =========================================================

  isError(issue: ValidationIssue): boolean {
    const severity = (issue.severidad ?? '').toLowerCase();

    return severity.includes('error');
  }

  isWarning(issue: ValidationIssue): boolean {
    const severity = (issue.severidad ?? '').toLowerCase();

    return severity.includes('warning') || severity.includes('advertencia');
  }

  // =========================================================
  // CONTADORES
  // =========================================================

  get totalErrors(): number {
    return this.issues.filter((issue) => this.isError(issue)).length;
  }

  get totalWarnings(): number {
    return this.issues.filter((issue) => this.isWarning(issue)).length;
  }

  // =========================================================
  // INCIDENCIAS FILTRADAS
  // =========================================================

  get filteredIssues(): ValidationIssue[] {
    const search = this.issueSearch.trim().toLowerCase();

    return this.issues.filter((issue) => {
      const matchesSearch =
        !search ||
        [
          issue.nombre_archivo,
          issue.hoja,
          issue.columna,
          issue.valor ?? '',
          issue.mensaje,
          issue.severidad,
        ].some((value) =>
          String(value ?? '')
            .toLowerCase()
            .includes(search),
        );

      const matchesSeverity =
        this.issueSeverity === 'all' ||
        (this.issueSeverity === 'error' && this.isError(issue)) ||
        (this.issueSeverity === 'warning' && this.isWarning(issue));

      const matchesFile = !this.issueFile || issue.nombre_archivo === this.issueFile;

      const matchesColumn = !this.issueColumn || issue.columna === this.issueColumn;

      return matchesSearch && matchesSeverity && matchesFile && matchesColumn;
    });
  }

  // =========================================================
  // LIMPIAR FILTROS
  // =========================================================

  clearIssueFilters(): void {
    this.issueSearch = '';
    this.issueSeverity = 'all';
    this.issueFile = '';
    this.issueColumn = '';
  }

  // =========================================================
  // LIMPIAR CONSULTA
  // =========================================================

  clearSearch(): void {
    this.validationId = '';
    this.validation = null;
    this.issues = [];

    this.hasSearched = false;
    this.errorMessage = '';

    this.clearIssueFilters();

    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: {},
      replaceUrl: true,
    });

    this.cdr.detectChanges();
  }
}
