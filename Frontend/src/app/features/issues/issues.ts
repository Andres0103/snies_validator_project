
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
  // PAGINACIÓN
  // =========================================================

  readonly pageSize = 15;

  currentPage = 1;

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

    this.validation = null;
    this.issues = [];

    this.clearIssueFilters();
    this.resetPagination();

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

      this.issues = record.issues ?? [];

      const issuesLoaded =
        record.issuesLoadedSuccessfully ?? this.issues.length > 0;

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
        issuesLoaded,
      );

      this.resetPagination();
      this.cdr.detectChanges();

      void this.updateUrl(record.id);

    } catch (error) {
      console.error('[ISSUES] Error consultando validación:', error);

      this.errorMessage =
        'No fue posible consultar el registro almacenado localmente.';

      this.validation = null;
      this.issues = [];

    } finally {
      this.isLoading = false;

      console.log('[ISSUES] Consulta finalizada. isLoading:', this.isLoading);

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
    return [
      ...new Set(this.issues.map(issue => issue.nombre_archivo)),
    ].sort();
  }

  get issueColumns(): string[] {
    return [
      ...new Set(this.issues.map(issue => issue.columna)),
    ].sort();
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

    return (
      severity.includes('warning') ||
      severity.includes('advertencia')
    );
  }

  // =========================================================
  // CONTADORES
  // =========================================================

  get totalErrors(): number {
    return this.issues.filter(issue => this.isError(issue)).length;
  }

  get totalWarnings(): number {
    return this.issues.filter(issue => this.isWarning(issue)).length;
  }

  // =========================================================
  // INCIDENCIAS FILTRADAS
  // =========================================================

  get filteredIssues(): ValidationIssue[] {
    const search = this.issueSearch.trim().toLowerCase();

    return this.issues.filter(issue => {

      const matchesSearch =
        !search ||
        [
          issue.nombre_archivo,
          issue.hoja,
          issue.columna,
          issue.valor ?? '',
          issue.mensaje,
          issue.severidad,
        ].some(value =>
          String(value ?? '').toLowerCase().includes(search)
        );

      const matchesSeverity =
        this.issueSeverity === 'all' ||
        (this.issueSeverity === 'error' && this.isError(issue)) ||
        (this.issueSeverity === 'warning' && this.isWarning(issue));

      const matchesFile =
        !this.issueFile ||
        issue.nombre_archivo === this.issueFile;

      const matchesColumn =
        !this.issueColumn ||
        issue.columna === this.issueColumn;

      return (
        matchesSearch &&
        matchesSeverity &&
        matchesFile &&
        matchesColumn
      );
    });
  }

  // =========================================================
  // PAGINACIÓN: CÁLCULOS
  // =========================================================

  get totalPages(): number {
    return Math.max(
      1,
      Math.ceil(this.filteredIssues.length / this.pageSize)
    );
  }

  get paginatedIssues(): ValidationIssue[] {
    const start = (this.currentPage - 1) * this.pageSize;

    return this.filteredIssues.slice(
      start,
      start + this.pageSize
    );
  }

  get startItem(): number {
    if (this.filteredIssues.length === 0) {
      return 0;
    }

    return (this.currentPage - 1) * this.pageSize + 1;
  }

  get endItem(): number {
    return Math.min(
      this.currentPage * this.pageSize,
      this.filteredIssues.length
    );
  }

  get hasPreviousPage(): boolean {
    return this.currentPage > 1;
  }

  get hasNextPage(): boolean {
    return this.currentPage < this.totalPages;
  }

  // =========================================================
  // PAGINACIÓN: NAVEGACIÓN
  // =========================================================

  resetPagination(): void {
    this.currentPage = 1;
  }

  firstPage(): void {
    this.currentPage = 1;
  }

  previousPage(): void {
    if (this.hasPreviousPage) {
      this.currentPage--;
    }
  }

  nextPage(): void {
    if (this.hasNextPage) {
      this.currentPage++;
    }
  }

  lastPage(): void {
    this.currentPage = this.totalPages;
  }

  // =========================================================
  // LIMPIAR FILTROS
  // =========================================================

  clearIssueFilters(): void {
    this.issueSearch = '';
    this.issueSeverity = 'all';
    this.issueFile = '';
    this.issueColumn = '';

    this.resetPagination();
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
    this.resetPagination();

    void this.router.navigate([], {
      relativeTo: this.route,
      queryParams: {},
      replaceUrl: true,
    });

    this.cdr.detectChanges();
  }
}
