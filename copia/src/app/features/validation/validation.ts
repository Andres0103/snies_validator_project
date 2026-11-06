import { Component } from '@angular/core';

@Component({
  selector: 'app-validation',
  standalone: true,
  imports: [],
  templateUrl: './validation.html',
  styleUrl: './validation.scss'
})
export class Validation {

  selectedFiles: File[] = [];
  errorMessage = '';

  onFilesSelected(event: Event): void {
    const input = event.target as HTMLInputElement;

    if (!input.files) {
      return;
    }

    const files = Array.from(input.files);

    const validFiles = files.filter(file =>
      file.name.toLowerCase().endsWith('.xlsx')
    );

    if (validFiles.length !== files.length) {
      this.errorMessage =
        'Solo se permiten archivos Excel con extensión .xlsx.';
    } else {
      this.errorMessage = '';
    }

    for (const file of validFiles) {

      const alreadyExists = this.selectedFiles.some(
        selected =>
          selected.name === file.name &&
          selected.size === file.size &&
          selected.lastModified === file.lastModified
      );

      if (!alreadyExists) {
        this.selectedFiles.push(file);
      }
    }

    input.value = '';
  }

  removeFile(index: number): void {
    this.selectedFiles.splice(index, 1);
  }

  validateFiles(): void {

    if (this.selectedFiles.length === 0) {
      this.errorMessage =
        'Debes seleccionar al menos un archivo para validar.';

      return;
    }

    console.log(
      'Archivos preparados para validación:',
      this.selectedFiles
    );

    // Posteriormente conectaremos este método con FastAPI.
  }

}