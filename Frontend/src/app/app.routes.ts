
import { Routes } from '@angular/router';

import { MainLayout } from './layout/main-layout/main-layout';
import { Dashboard } from './features/dashboard/dashboard';

export const routes: Routes = [
  {
    path: '',
    component: MainLayout,
    children: [
      {
        path: '',
        component: Dashboard,
        title: 'Inicio | NEBULA',
        data: {
          headerTitle: 'Panel principal',
          headerDescription: 'Sistema de gestión y validación de información SNIES'
        }
      },
      {
        path: 'validation',
        loadComponent: () =>
          import('./features/validation/validation')
            .then(m => m.Validation),
        title: 'Validación | SNIES',
        data: {
          headerTitle: 'Validación de información',
          headerDescription: 'Carga y validación de archivos de información SNIES'
        }
      },
      {
        path: 'history',
        loadComponent: () =>
          import('./features/history/history')
            .then(m => m.History),
        title: 'Historial | SNIES',
        data: {
          headerTitle: 'Historial de procesos',
          headerDescription: 'Consulta los procesos de validación ejecutados'
        }
      },
      {
        path: 'issues',
        loadComponent: () =>
          import('./features/issues/issues')
            .then(m => m.Issues),
        title: 'Consulta de incidencias | NEBULA',
        data: {
          headerTitle: 'Consulta de incidencias',
          headerDescription: 'Consulta y análisis de errores y advertencias de validación'
        }
      },
    ]
  },
  {
    path: '**',
    redirectTo: ''
  }
];
