
import { Routes } from '@angular/router';

import { MainLayout } from './layout/main-layout/main-layout';

import { Dashboard } from './features/dashboard/dashboard';
import { Validation } from './features/validation/validation';
import { History } from './features/history/history';
import { Issues } from './features/issues/issues';

export const routes: Routes = [
  {
    path: '',
    component: MainLayout,
    children: [
      {
        path: '',
        component: Dashboard,
        title: 'Inicio | SNIES',
        data: {
          headerTitle: 'Panel principal',
          headerDescription: 'Sistema de gestión y validación de información SNIES'
        }
      },
      {
        path: 'validation',
        component: Validation,
        title: 'Validación | SNIES',
        data: {
          headerTitle: 'Validación de información',
          headerDescription: 'Carga y validación de archivos de información SNIES'
        }
      },
      {
        path: 'history',
        component: History,
        title: 'Historial | SNIES',
        data: {
          headerTitle: 'Historial de procesos',
          headerDescription: 'Consulta los procesos de validación ejecutados'
        }
      },
      {
        path: 'issues',
        component: Issues,
        title: 'Consulta de incidencias | SNIES',
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
