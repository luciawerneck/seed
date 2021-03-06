/**
 * :copyright (c) 2014 - 2018, The Regents of the University of California, through Lawrence Berkeley National Laboratory (subject to receipt of any required approvals from the U.S. Department of Energy) and contributors. All rights reserved.
 * :author
 */
angular.module('BE.seed.controller.show_populated_columns_modal', [])
  .controller('show_populated_columns_modal_controller', [
    '$scope',
    '$window',
    '$uibModalInstance',
    'Notification',
    'inventory_service',
    'spinner_utility',
    'columns',
    'cycle_id',
    'inventory_type',
    function ($scope, $window, $uibModalInstance, Notification, inventory_service, spinner_utility, columns, cycle_id, inventory_type) {
      $scope.columns = columns;
      $scope.cycle_id = cycle_id;
      $scope.inventory_type = inventory_type;

      _.forEach($scope.columns, function (col) {
        col.pinnedLeft = false;
        col.visible = true;
      });

      var notEmpty = function (value) {
        return !_.isNil(value) && value !== '';
      };

      $scope.start = function () {
        $scope.state = 'running';
        $scope.status = 'Fetching Inventory';

        var promise;
        var columnNames = _.map(inventory_service.loadSettings(null, columns), 'name');
        if ($scope.inventory_type === 'properties') {
          promise = inventory_service.get_properties(1, undefined, cycle_id, columnNames).then(function (inv) {
            return inv.results;
          });
        } else if ($scope.inventory_type === 'taxlots') {
          promise = inventory_service.get_taxlots(1, undefined, cycle_id, columnNames).then(function (inv) {
            return inv.results;
          });
        }

        promise.then(function (inventory) {
          $scope.progress = 50;
          $scope.status = 'Processing ' + $scope.columns.length + ' columns in ' + inventory.length + ' records';

          var cols = _.reject($scope.columns, 'related');
          // console.log('cols', cols);

          var relatedCols = _.filter($scope.columns, 'related');
          // console.log('relatedCols', relatedCols);

          _.forEach(inventory, function (record, index) {
            // console.log(cols.length + ' remaining cols to check');
            _.forEachRight(cols, function (col, colIndex) {
              if (notEmpty(record[col.dbName])) {
                // console.log('Removing ' + col.dbName + ' from cols');
                cols.splice(colIndex, 1);
              }
            });

            _.forEach(record.related, function (relatedRecord) {
              // console.log(relatedCols.length + ' remaining related cols to check');
              _.forEachRight(relatedCols, function (col, colIndex) {
                if (notEmpty(relatedRecord[col.dbName])) {
                  // console.log('Removing ' + col.dbName + ' from relatedCols');
                  relatedCols.splice(colIndex, 1);
                }
              });
            });

            $scope.progress = index / inventory.length * 50 + 50;
          });

          // determine hidden columns
          var visible = _.reject($scope.columns, function (col) {
            if (!col.related) {
              return _.find(cols, {dbName: col.dbName, table: col.table});
            }
            return _.find(relatedCols, {dbName: col.dbName, table: col.table});
          });

          var hidden = _.reject($scope.columns, function (col) {
            return _.find(visible, {dbName: col.dbName, table: col.table});
          });

          _.forEach(hidden, function (col) {
            col.visible = false;
          });

          // console.log(visible.concat(hidden));

          inventory_service.saveSettings('grid.' + $scope.inventory_type, visible.concat(hidden));

          $scope.progress = 100;
          $scope.state = 'done';
          $scope.status = 'Found ' + visible.length + ' populated columns';
        });
      };

      $scope.refresh = function () {
        spinner_utility.show();
        $window.location.reload();
      };

      $scope.cancel = function () {
        $uibModalInstance.dismiss();
      };
    }]);
