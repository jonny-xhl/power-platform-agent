// Phase 7 ribbon smoke library — also a reference for HOW RIBBON PASSES PARAMETERS TO JS.
//
// Ribbon passes <CrmParameter Value="..."> to these functions POSITIONALLY, in declaration order (no Name).
// This is a FORM button, so the tool passes PrimaryControl => the JS receives the formContext as arg 1.
// (Grid buttons pass SelectedControl => gridContext. Full table in the dv-ribbon-python skill.)

// Click handler — command <Actions><JavaScriptFunction>. primaryControl IS the formContext. No return needed.
function onSmokeClick(primaryControl) {
    var fc = primaryControl;                       // formContext
    var id = fc.data.entity.getId();               // current record id, e.g. "{guid}"
    console.log('ribbon smoke clicked, id=' + id);
    // read a field:   fc.getAttribute("statuscode").getValue();
    // refresh form:   fc.data.refresh();
    // save:           fc.data.entity.save();
}

// Visibility (EnableRule <CustomRule>) — returns bool (true = show). primaryControl = formContext.
// Unified Interface also accepts a Promise (10s timeout => treated as false).
// Default="false" (custom-button fail-closed): if this JS fails to load, the button HIDES.
function shouldShowSmoke(primaryControl) {
    var fc = primaryControl;                       // formContext
    // example: show only when statuscode == 1 (Active):
    //   return fc.getAttribute("statuscode").getValue() === 1;
    return true;
}

// OOB Deactivate visibility (customise_command). Returns bool (true = show). Default="true" (fail-OPEN for OOB
// — if JS fails, the Deactivate button keeps its normal behaviour).
function shouldShowDeactivate(primaryControl) {
    var fc = primaryControl;                       // formContext
    // example: hide Deactivate once approved:
    //   return fc.getAttribute("statuscode").getValue() !== 100003;
    return true;
}
