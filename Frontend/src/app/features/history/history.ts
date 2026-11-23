import {
  Component,
  OnInit,
  inject,
  ChangeDetectorRef,
  ElementRef,
  ViewChild,
} from '@angular/core';

import { ActivatedRoute, Router } from '@angular/router';

import { ValidationHistoryService } from '../../core/services/validation-history.service';

import {
  LocalValidationRecord,
  StoredValidationFile,
} from '../../core/models/validation-history.model';

import { ValidationIssue } from '../../core/models/validation.model';

import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-history',
  standalone: true,
  imports: [FormsModule],
  templateUrl: './history.html',
  styleUrl: './history.scss',
})
export class History implements OnInit {
  // =========================================================
  // SERVICIOS
  // =========================================================

  private historyService = inject(ValidationHistoryService);

  private cdr = inject(ChangeDetectorRef);

  private route = inject(ActivatedRoute);

  private router = inject(Router);

  // =========================================================
  // REFERENCIAS DOM
  // =========================================================

  @ViewChild('historyTop')
  private historyTop?: ElementRef<HTMLElement>;

  @ViewChild('historyDetail')
  private historyDetail?: ElementRef<HTMLElement>;

  // =========================================================
  // PROPIEDADES DEL HISTORIAL
  // =========================================================

  validations: LocalValidationRecord[] = [];

  selectedValidation: LocalValidationRecord | null = null;

  issues: ValidationIssue[] = [];

  // =========================================================
  // FILTROS DE INCIDENCIAS
  // =========================================================

  issueSearch = '';

  issueSeverity = 'all';

  issueFile = '';

  issueColumn = '';

  get issueFiles(): string[] {
    return [
      ...new Set(
        this.issues
          .map((issue) => issue.nombre_archivo)
          .filter(Boolean),
      ),
    ].sort((a, b) => a.localeCompare(b));
  }

  get issueColumns(): string[] {
    return [
      ...new Set(
        this.issues
          .map((issue) => issue.columna)
          .filter(Boolean),
      ),
    ].sort((a, b) => a.localeCompare(b));
  }

  // =========================================================
  // NAVEGACIÓN A INCIDENCIAS
  // =========================================================

  goToIssues(validation: LocalValidationRecord): void {
    void this.router.navigate(['/issues'], {
      queryParams: {
        id: validation.id,
      },
    });
  }

  // =========================================================
  // CLASIFICACIÓN DE INCIDENCIAS
  // =========================================================

  private getIssueType(
    severity: string,
  ): 'error' | 'warning' | 'other' {
    const normalized = (severity ?? '').trim().toLowerCase();

    if (normalized.includes('error')) {
      return 'error';
    }

    if (
      normalized.includes('advertencia') ||
      normalized.includes('warning')
    ) {
      return 'warning';
    }

    return 'other';
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
          String(issue.fila),
        ].some((value) =>
          String(value).toLowerCase().includes(search),
        );

      const type = this.getIssueType(issue.severidad);

      const matchesSeverity =
        this.issueSeverity === 'all' ||
        type === this.issueSeverity;

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
  // LIMPIEZA DE FILTROS DE INCIDENCIAS
  // =========================================================

  clearIssueFilters(): void {
    this.issueSearch = '';
    this.issueSeverity = 'all';
    this.issueFile = '';
    this.issueColumn = '';
  }

  // =========================================================
  // CONTADORES DE INCIDENCIAS
  // =========================================================

  countIssues(type: 'error' | 'warning'): number {
    return this.issues.filter(
      (issue) => this.getIssueType(issue.severidad) === type,
    ).length;
  }

  // =========================================================
  // TRADUCCIÓN DE ESTADOS
  // =========================================================

  getStatusLabel(status: string | undefined | null): string {
    if (!status) {
      return 'No disponible';
    }

    const statusLabels: Record<string, string> = {
      COMPLETADO: 'Completado',
      COMPLETADO_CON_OBSERVACIONES: 'Completado con observaciones',
      COMPLETADO_PARCIAL: 'Completado parcialmente',
      FALLIDO: 'Fallido',
      PENDIENTE: 'Pendiente',
      PROCESANDO: 'Procesando',
    };

    return statusLabels[status] ?? status;
  }

  // =========================================================
  // FILTRO DE FECHA
  // =========================================================

  searchDate = '';

  // =========================================================
  // ESTADOS DE LA INTERFAZ
  // =========================================================

  isLoading = false;

  isLoadingIssues = false;

  errorMessage = '';

  // =========================================================
  // INICIALIZACIÓN
  // =========================================================

  ngOnInit(): void {
    void this.loadHistory();
  }

  // =========================================================
  // VALIDACIONES FILTRADAS POR FECHA
  // =========================================================

  get filteredValidations(): LocalValidationRecord[] {
    if (!this.searchDate) {
      return this.validations;
    }

    return this.validations.filter((validation) => {
      const date = new Date(validation.savedAt);

      if (Number.isNaN(date.getTime())) {
        return false;
      }

      const year = date.getFullYear();

      const month = String(date.getMonth() + 1).padStart(2, '0');

      const day = String(date.getDate()).padStart(2, '0');

      const recordDate = `${year}-${month}-${day}`;

      return recordDate === this.searchDate;
    });
  }

  // =========================================================
  // CAMBIO DE FECHA
  // =========================================================

  onDateChange(event: Event): void {
    const input = event.target as HTMLInputElement;

    this.searchDate = input.value;
  }

  // =========================================================
  // LIMPIEZA DE FECHA
  // =========================================================

  clearDateFilter(): void {
    this.searchDate = '';
  }

  // =========================================================
  // CARGA DEL HISTORIAL
  // =========================================================

  async loadHistory(): Promise<void> {
    this.isLoading = true;

    this.errorMessage = '';

    this.cdr.detectChanges();

    try {
      this.validations = await this.historyService.getAll();

      const selectedId =
        this.route.snapshot.queryParamMap.get('id');

      // Apertura desde Dashboard.
      if (selectedId) {
        const requestedValidation = this.validations.find(
          (validation) => validation.id === selectedId,
        );

        if (requestedValidation) {
          this.selectedValidation = requestedValidation;

          this.issues = requestedValidation.issues ?? [];

          this.clearIssueFilters();

          console.log(
            '[HISTORY] Validación abierta desde Dashboard:',
            selectedId,
          );
        } else {
          console.warn(
            '[HISTORY] No se encontró la validación solicitada:',
            selectedId,
          );
        }
      }

      console.log(
        '[HISTORY] Registros recuperados de IndexedDB:',
        this.validations.length,
      );

      // Actualizamos el registro seleccionado si ya estaba abierto.
      if (this.selectedValidation && !selectedId) {
        const updatedRecord = this.validations.find(
          (item) => item.id === this.selectedValidation?.id,
        );

        this.selectedValidation = updatedRecord ?? null;

        this.issues = updatedRecord?.issues ?? [];
      }
    } catch (error) {
      console.error(
        '[HISTORY] Error consultando IndexedDB:',
        error,
      );

      this.errorMessage =
        'No fue posible recuperar el historial almacenado en este navegador.';
    } finally {
      this.isLoading = false;

      this.cdr.detectChanges();

      if (this.selectedValidation) {
        this.scrollToDetail();
      }
    }
  }

  // =========================================================
  // CONSULTA DEL DETALLE
  // =========================================================

  viewDetails(validation: LocalValidationRecord): void {
    this.selectedValidation = validation;

    this.issues = validation.issues ?? [];

    this.isLoadingIssues = false;

    this.errorMessage = '';

    this.clearIssueFilters();

    console.log(
      '[HISTORY] Detalle consultado:',
      validation.id,
    );

    this.scrollToDetail();
  }

  // =========================================================
  // DESPLAZAMIENTO HASTA EL DETALLE
  // =========================================================

  private scrollToDetail(): void {
    this.cdr.detectChanges();

    requestAnimationFrame(() => {
      const detailElement =
        this.historyDetail?.nativeElement;

      const scrollContainer =
        document.querySelector('.page-content') as HTMLElement | null;

      if (!detailElement || !scrollContainer) {
        console.warn(
          '[HISTORY] No se encontró el detalle o el contenedor scroll.',
        );

        return;
      }

      const containerRect =
        scrollContainer.getBoundingClientRect();

      const detailRect =
        detailElement.getBoundingClientRect();

      const offset = 20;

      const targetPosition =
        scrollContainer.scrollTop +
        detailRect.top -
        containerRect.top -
        offset;

      scrollContainer.scrollTo({
        top: Math.max(0, targetPosition),
        behavior: 'smooth',
      });
    });
  }

  // =========================================================
  // DESPLAZAMIENTO AL HISTORIAL
  // =========================================================

  scrollToHistoryTop(): void {
    const element = this.historyTop?.nativeElement;

    const scrollContainer =
      document.querySelector('.page-content') as HTMLElement | null;

    if (!element || !scrollContainer) {
      return;
    }

    const containerRect =
      scrollContainer.getBoundingClientRect();

    const elementRect =
      element.getBoundingClientRect();

    const targetPosition =
      scrollContainer.scrollTop +
      elementRect.top -
      containerRect.top -
      20;

    scrollContainer.scrollTo({
      top: Math.max(0, targetPosition),
      behavior: 'smooth',
    });
  }

  // =========================================================
  // CERRAR DETALLE
  // =========================================================

  closeDetails(): void {
    this.selectedValidation = null;

    this.issues = [];

    this.isLoadingIssues = false;
  }

  // =========================================================
  // DESCARGA DEL REPORTE
  // =========================================================

  downloadReport(validation: LocalValidationRecord): void {
    if (!validation.report?.blob) {
      this.errorMessage =
        'Esta validación no tiene un reporte consolidado almacenado.';

      return;
    }

    this.downloadStoredFile(
      validation.report,
      `reporte_validacion_${validation.id}.xlsx`,
    );
  }

  // =========================================================
  // DESCARGA DE ARCHIVO MARCADO
  // =========================================================

  downloadMarkedFile(
    validation: LocalValidationRecord,
    filename: string,
  ): void {
    const file = validation.generatedFiles?.find(
      (item) => item.name === filename,
    );

    if (!file) {
      this.errorMessage =
        `No se encontró el archivo marcado: ${filename}`;

      return;
    }

    this.downloadStoredFile(file, file.name);
  }

  // =========================================================
  // DESCARGA DE ARCHIVO ORIGINAL
  // =========================================================

  downloadOriginalFile(
    validation: LocalValidationRecord,
    filename: string,
  ): void {
    const file = validation.originalFiles?.find(
      (item) => item.name === filename,
    );

    if (!file) {
      this.errorMessage =
        `No se encontró el archivo original: ${filename}`;

      return;
    }

    this.downloadStoredFile(file, file.name);
  }

  // =========================================================
  // DESCARGA GENÉRICA
  // =========================================================

  private downloadStoredFile(
    file: StoredValidationFile,
    filename: string,
  ): void {
    try {
      const url = window.URL.createObjectURL(file.blob);

      const link = document.createElement('a');

      link.href = url;

      link.download = filename;

      document.body.appendChild(link);

      link.click();

      link.remove();

      window.setTimeout(() => {
        window.URL.revokeObjectURL(url);
      }, 1000);
    } catch (error) {
      console.error(
        '[HISTORY] Error descargando archivo:',
        error,
      );

      this.errorMessage =
        'No fue posible descargar el archivo almacenado.';
    }
  }

  // =========================================================
  // FORMATO DE FECHAS
  // =========================================================

  formatDate(value: string | undefined | null): string {
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
}