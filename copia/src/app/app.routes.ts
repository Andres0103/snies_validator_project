import { Routes } from '@angular/router';

import { MainLayout } from './layout/main-layout/main-layout';

import { Dashboard } from './features/dashboard/dashboard';
import { Validation } from './features/validation/validation';
import { History } from './features/history/history';

export const routes: Routes = [
  {
    path: '',
    component: MainLayout,
    children: [
      {
        path: '',
        component: Dashboard,
        title: 'Inicio | SNIES'
      },
      {
        path: 'validation',
        component: Validation,
        title: 'Validación | SNIES'
      },
      {
        path: 'history',
        component: History,
        title: 'Historial | SNIES'
      }
    ]
  },
  {
    path: '**',
    redirectTo: ''
  }
];