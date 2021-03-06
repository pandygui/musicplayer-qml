
function loadqml(qmlfile, parent, properties) {

    var instance;
    var component;
    function finishCreation() {
        if (component.status == Component.Ready) {
            instance = component.createObject(parent, properties);
            if (instance == null) {
                // Error Handling
                console.log("Error creating object");
            }
            parent.push(instance);
        } else if (component.status == Component.Error) {
            // Error Handling
            console.log("Error loading component:", component.errorString());
        }
    }

    component = Qt.createComponent(qmlfile);
    if (component.status == Component.Ready){
        instance = component.createObject(parent, properties);
        parent.push(instance);
    }
    else
        component.statusChanged.connect(finishCreation);
}
