// test new orgs and sub orgs
var EC = protractor.ExpectedConditions;
// Accounts page
describe('When I visit the accounts page', function () {
    it('should see my organizations', function () {
        browser.ignoreSynchronization = false;
        browser.get("/app/#/accounts");

        var rows = element.all(by.repeater('org in orgs_I_own'));
        expect(rows.count()).not.toBeLessThan(1);
    });
    it('should find and create new sub org', function () {
        var myNewOrg = element(by.cssContainingText('.account_org.parent_org', browser.params.testOrg.parent))
            .element(by.xpath('..')).element(by.xpath('..'));
        expect(myNewOrg.isPresent()).toBe(true);

        browser.actions().mouseMove(myNewOrg.$('[ng-show="org.is_parent"]').$('.sub_head.sub_org.right')).perform();
        myNewOrg.$('.sub_head.sub_org.right').$$('a').first().click(); 
        $('[id="createOrganizationName"]').sendKeys(browser.params.testOrg.child);
        $('[id="createOrganizationInvite"]').sendKeys(browser.params.login.user);
        $('.btn.btn-primary').click();
        
        var myNewSub = element(by.cssContainingText('.account_org.left', browser.params.testOrg.child))
            .element(by.xpath('..'));
        
        // expect(myNewSub.count() > 0);
        expect(myNewSub.isPresent()).toBe(true);
        browser.actions().mouseMove(myNewSub.$('.account_org.right')).perform();
        myNewSub.$$('.account_org.right a').first().click();
    });
    it('should change the sub org name', function () {
        $('input').clear().then(function() {
            $('input').sendKeys(browser.params.testOrg.childRename);
            $$('[ng-click="save_settings()"]').first().click();
            expect($('.page_title').getText()).toEqual(browser.params.testOrg.childRename);
        });
    });
    it('should go back to orgranizations', function () {
        $('[ui-sref="organizations"]').click();
        expect($('.page_title').getText()).toEqual('Organizations');
    });
});
describe('When I visit the the parent org', function () {
    it('should go to parent organization', function () {
        var myNewOrg = element(by.cssContainingText('.account_org.parent_org', browser.params.testOrg.parent))
            .element(by.xpath('..')).$('.account_org.right');
        
        expect(myNewOrg.isPresent()).toBe(true);

        browser.actions().mouseMove(myNewOrg).perform();
        myNewOrg.$$('a').first().click();
        var myOptions = element.all(by.css('a')).filter(function (elm) {
            return elm.getText().then(function(label) { 
                return label == 'Cycles';
            });
        }).first();
        myOptions.click();
        expect($('.table_list_container').isPresent()).toBe(true);
    });

    it('should create new cycle', function () {
        $('[ng-model="new_cycle.name"]').sendKeys('faketest121212');
        $('[ng-model="new_cycle.start"]').sendKeys('01-01-2017');
        $('[ng-model="new_cycle.end"]').sendKeys('12-31-2017');
        $('#btnCreateCycle').click();
    });    
    
    it('should edit created cycle', function () {
        $$('.btn-default.btn-rowform').last().click();
        var editCycle = $$('.editable-wrap.editable-text').first();
        editCycle.$('.ng-not-empty').clear().then(function(){
            editCycle.$('.ng-empty').sendKeys(browser.params.testOrg.cycle);                  
        });

        $$('.btn-primary.btn-rowform').last().click(); 
        var myNewCycle = element.all(by.repeater('cycle in cycles')).filter(function(sub) {
            return sub.all(by.tagName('td')).first().$('[ng-show="!rowform.$visible"]').getText().then(function(label) { 
                return label == browser.params.testOrg.cycle;
            });
        }).first();
        expect(myNewCycle.all(by.tagName('td')).first().$('[ng-show="!rowform.$visible"]').getText()).toEqual(browser.params.testOrg.cycle);
    });

    it('should create new label', function () {
        var myOptions = element.all(by.css('a')).filter(function (elm) {
            return elm.getText().then(function(label) { 
                return label == 'Labels';
            });
        }).first();
        myOptions.click();
        
        $$('input').first().sendKeys('fake label');
        $('.input-group-btn.dropdown').click();
        element(by.cssContainingText('.dropdown-menu.pull-right', 'orange')).click();
        $('#btnCreateLabel').click();
        var myNewLabel = element(by.cssContainingText('[editable-text="label.name"]', 'fake label'))
            .element(by.xpath('..')).element(by.xpath('..'));

        expect(myNewLabel.isPresent()).toBe(true);
        myNewLabel.$('[ng-click="deleteLabel(label, $index)"]').click();
        browser.sleep(300);
        $('.btn.btn-primary.ng-binding').click();
        expect(myNewLabel.isPresent()).toBe(false);
    });

    it('should go to parent organization and select Sharing', function () {
        var myOptions3 = element.all(by.css('a')).filter(function (elm) {
            return elm.getText().then(function(label) { 
                return label == 'Sharing';
            });
        }).first();
        myOptions3.click();
        expect($('.table_list_container').isPresent()).toBe(true);
        $$('[ng-model="controls.public_select_all"]').first().click();
        var rowCheck = element.all(by.repeater('field in fields'));
        expect(rowCheck.count()).not.toBeLessThan(1); 
        $$('[ng-model="filter_params.title"]').first().click().sendKeys('this is some fake stuff to test filter');
        expect(rowCheck.count()).toBe(0);
        $$('[ng-model="filter_params.title"]').first().click().clear();
        expect(rowCheck.count()).not.toBeLessThan(1); 
        $$('[ng-click="save_settings()"]').first().click();
        browser.wait(EC.presenceOf($('.fa-check')),10000);
    });

});
