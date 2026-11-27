
import { Routes } from '@angular/router';

import { MainLayout } from './layout/main-layout/main-layout';
import { Dashboard } from './features/dashboard/dashboard';

export const routes: Routes = [
  {
    path: '',
    component: MainLayout,
    children: [
      // INICIO
      {
        path: '',
        component: Dashboard,
        title: 'Inicio | NEBULA',
        data: {
          headerTitle: 'Panel principal',
          headerDescription:
            'Sistema de gestión y validación de información SNIES'
        }
      },

      // VALIDACIÓN GENERAL
      {
        path: 'validation',
        loadComponent: () =>
          import('./features/validation/validation')
            .then(m => m.Validation),
        title: 'Validación | NEBULA',
        data: {
          headerTitle: 'Validación de información',
          headerDescription:
            'Carga y validación general de archivos de información'
        }
      },

      // EXTENSIÓN - HISTORIAL
      {
        path: 'extension/history',
        loadComponent: () =>
          import('./features/history/history')
            .then(m => m.History),
        title: 'Historial de Extensión | NEBULA',
        data: {
          modulo: 'extension',
          headerTitle: 'Historial de Extensión',
          headerDescription:
            'Consulta los procesos de validación del módulo de Extensión'
        }
      },

      // EXTENSIÓN - INCIDENCIAS
      {
        path: 'extension/issues',
        loadComponent: () =>
          import('./features/issues/issues')
            .then(m => m.Issues),
        title: 'Incidencias de Extensión | NEBULA',
        data: {
          modulo: 'extension',
          headerTitle: 'Incidencias de Extensión',
          headerDescription:
            'Consulta los errores y advertencias de Extensión'
        }
      },

      // SNIES - HISTORIAL
      {
        path: 'snies/history',
        loadComponent: () =>
          import('./features/history/history')
            .then(m => m.History),
        title: 'Historial SNIES | NEBULA',
        data: {
          modulo: 'snies',
          headerTitle: 'Historial de Población Estudiantil',
          headerDescription:
            'Consulta los procesos de validación de plantillas SNIES'
        }
      },

      // SNIES - INCIDENCIAS
      {
        path: 'snies/issues',
        loadComponent: () =>
          import('./features/issues/issues')
            .then(m => m.Issues),
        title: 'Incidencias SNIES | NEBULA',
        data: {
          modulo: 'snies',
          headerTitle: 'Incidencias de Población Estudiantil',
          headerDescription:
            'Consulta los errores y advertencias de las plantillas SNIES'
        }
      },

      // COMPATIBILIDAD CON LAS RUTAS ANTERIORES
      {
        path: 'history',
        redirectTo: 'extension/history',
        pathMatch: 'full'
      },
      {
        path: 'issues',
        redirectTo: 'extension/issues',
        pathMatch: 'full'
      }
    ]
  },

  // RUTA NO ENCONTRADA
  {
    path: '**',
    redirectTo: ''
  }
];
