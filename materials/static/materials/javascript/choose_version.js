'use strict';


function plot_data(element, data, x_title, x_unit, y_title, y_unit) {
  const ctx = document.getElementById(element).getContext('2d');
  const datasets = [];
  const colors = [
    'rgb(89,112,216)', 'rgb(100,194,78)', 'rgb(162,88,201)', 'rgb(175,182,56)',
    'rgb(210,71,153)', 'rgb(80,144,44)', 'rgb(202,141,217)', 'rgb(75,189,128)',
    'rgb(211,68,88)', 'rgb(77,191,183)', 'rgb(208,88,49)', 'rgb(94,152,211)',
    'rgb(214,155,70)', 'rgb(122,94,160)', 'rgb(153,178,109)', 'rgb(156,69,98)',
    'rgb(58,128,80)', 'rgb(223,131,154)', 'rgb(116,115,42)', 'rgb(170,106,64)'
  ]
  for (let i = 0; i < data.length; i++) {
    datasets.push({
      label: data[i]['legend'],
      backgroundColor: 'rgba(0,0,0,0)',
      borderColor: colors[i],
      data: data[i]['values']
    });
  }
  const chart = new Chart(ctx, {
    type: 'scatter',
    data: {datasets: datasets},
    options: {
      scales: {
        xAxes: [{
          type: 'linear',
          scaleLabel: {
            display: true,
            labelString: x_title + ', ' + x_unit,
            fontSize: 14,
          },
        }],
        yAxes: [{
          type: 'linear',
          scaleLabel: {
            display: true,
            labelString: y_title + ', ' + y_unit,
            fontSize: 14,
          },
        }]
      }
    }
  });
}

for (let element of document.getElementsByClassName('choose-version')) {
  let compound_pk = element.id.split('choose_version_')[1].split('_')[0];
  let property_pk = element.id.split('choose_version_')[1].split('_')[1];
  // Construct the version selection fields
  axios
    .get('/materials/dataset-versions/' + compound_pk + '/' + property_pk)
    .then(response => {
      for (let x of response.data.data) {
        let opt = document.createElement('option');
        opt.value = x['pk'];
        opt.innerHTML = x['updated'] + ' --By: ' + x['updated_by__username'];
        element.appendChild(opt);
      }
    });
  // Show data of selected version for each property (dataset)
  element.addEventListener('change', function() {
    if (element.value !== "0") {
      // Change the pk parameter of edit button
      document
      .getElementById('edit_' + property_pk)
      .href = "/materials/update-dataset/" + element.value;

      axios
      .get('/materials/dataset-details/' + element.value)
      .then(response => {
        let data = response['data'];
        // general
        document.getElementById('general_card_' + property_pk).hidden = false;
        let general_el = document.getElementById('id_general_' + property_pk);
        general_el.innerHTML = "";
        for (let [key, value] of Object.entries(data['general'])) {
          let p = document.createElement('p');
          p.innerHTML = `<strong>${key}:</strong> ${data['general'][key]}`;
          general_el.appendChild(p);
        }
        // synthesis/ experimental/ computational
        for (let title of ['synthesis', 'experimental', 'computational']) {
          if (Object.entries(data[title]).length !== 0) {
            document.getElementById(`${title}-card-${property_pk}`).hidden = false;
            let el = document.getElementById(`${title}-body-${property_pk}`)
                             .getElementsByClassName('card-body')[0];
            el.innerHTML = "";
            for (let [key, value] of Object.entries(data[title])) {
              if (value !== "") {
                let p = document.createElement('p');
                if (key === 'External repositories') {
                  p.innerHTML = `<strong>${key}:</strong> `;
                  let ul = document.createElement('ul');
                  for (let repo of data[title][key]) {
                    let li = document.createElement('li');
                    li.innerHTML = `<a href=${repo}>${repo}</a>`;
                    ul.appendChild(li);
                  }
                  p.appendChild(ul);
                } else {
                  p.innerHTML = `<strong>${key}:</strong> ${data[title][key]}`;
                }
                el.appendChild(p);
              }
            }
          } else {
            document.getElementById(`${title}-card-${property_pk}`).hidden = true;
          }
        }
        // data (subsets)
        document.getElementById('subsets_card_' + property_pk).hidden = false;
        let data_el = document.getElementById('id_subsets_' + property_pk);
        data_el.innerHTML = "";
        for (let [index, subset] of Object.entries(data['data'])) {
          let card = document.createElement('div');
          card.className = "card";
          let card_header = document.createElement('div');
          card_header.className = "card-header";
          card_header.innerHTML = `Subset #${index+1}: ${subset['title']}`;
          card.appendChild(card_header);
          let card_body = document.createElement('div');
          card_body.className = "card-body";
          
          if (subset['primary property'] === 'atomic structure') {
            // atomic structure data
            let root_el = document.createElement('div');
            root_el.className = "row";
            let left_el, right_el;
            left_el = document.createElement('div');
            left_el.className = "col-md-6"; 
            // atomic structure -lattice constants
            if ('lattice constants' in subset) {
              let atom = subset['lattice constants'];
              let atom_h = document.createElement('h5');
              atom_h.innerHTML = "<strong>Lattice constants: </strong>";
              left_el.appendChild(atom_h);
              let atom_d = document.createElement('div');
              atom_d.className = "text-center";
              if (atom.length > 0) {
                for (let a of atom) {
                  let atom_p = document.createElement('p');
                  atom_p.innerHTML = `<strong>${a['symbol']}: </strong>${a['value']}${a['unit']}`;
                  atom_d.appendChild(atom_p);
                }
                left_el.appendChild(atom_d);
              } else {
                let empty_p = document.createElement('p');
                empty_p.innerHTML = "No lattice constants available for this subset."
                left_el.appendChild(empty_p);
              }
            }
            //atomic structure -atomic coordinates
            if ('atomic coordinates' in subset) {
              let coord = subset['atomic coordinates'];
              let coord_h = document.createElement('h5');
              coord_h.innerHTML = "<strong>Atomic coordinates: <strong>";
              left_el.appendChild(coord_h);
              let coord_t = document.createElement('table');
              coord_t.className = "table table-sm";
              if (coord.length > 0) {
                let tr, td;
                for (let c of coord) {
                  tr = document.createElement('tr');
                  for (let v of Object.values(c)) {
                    td = document.createElement('td');
                    td.innerHTML = `${v}`;
                    td.style = 'text-align:left';
                    tr.append(td);
                  }
                  coord_t.append(tr);
                }
              } else {
                coord_t.innerHTML = "Atomic coordinates not available for this subset.";
              }
              left_el.appendChild(coord_t);
            }
            root_el.appendChild(left_el);

            right_el = document.createElement('div');
            right_el.className = "col-md-6";
            // jsmol structure
            let jsmol_h = document.createElement('h5');
            jsmol_h.innerHTML = "<strong>3D Atomic structure: </strong>";
            right_el.appendChild(jsmol_h);
            let jsmol_d = document.createElement('div');
            jsmol_d.id = `id_jsmol_${subset['pk']}`;
            $.get('get-jsmol-input/' + subset['pk'], function(response) {
              if (response !== "") {
                $('#id_jsmol_' + subset['pk']).html(Jmol.getAppletHtml('jmol', {
                  script: response,
                  j2sPath: "/static/jsmol/j2s",
                  height: 450,
                  width: 470,
                }));
              } else {
                jsmol_d.innerHTML = 'Jsmol 3D atomic structre not available.';
              }
            });
            right_el.appendChild(jsmol_d);
            root_el.appendChild(right_el);

            card_body.appendChild(root_el);
          } else if (subset['primary property'] === 'tolerance factor related parameters') {
            // bond lengths & tolerance factors
            let root_el = document.createElement('div');
            let heads = ['bond lengths', 'tolerance factors'];
            for (let head of heads) {
              if (head in subset) {
                let tf = subset[head];
                let el_h = document.createElement('h5');
                let h_text = head.charAt(0).toUpperCase() + head.slice(1);
                el_h.innerHTML = `<strong>${h_text}: <strong>`;
                root_el.appendChild(el_h);
                let el_t = document.createElement('table');
                el_t.className = "table table-sm";
                if (tf.length > 0) {
                  let tr, th, td;
                  tr = document.createElement('tr');
                  for (let k of Object.keys(tf[0])) {
                    th = document.createElement('th');
                    th.innerHTML = `${k}`;
                    th.scope = "col";
                    tr.append(th);
                  }
                  el_t.append(tr);
                  for (let b of tf) {
                    tr = document.createElement('tr');
                    for (let v of Object.values(b)) {
                      td = document.createElement('td');
                      td.innerHTML = `${v}`;
                      td.style = 'text-align:left';
                      tr.append(td);
                    }
                    el_t.append(tr);
                  }
                } else {
                  el_t.innerHTML = "No bond lengths data for this subset.";
                }
                root_el.appendChild(el_t);
              }
            }
            card_body.appendChild(root_el);
          } else {
            // normal properties
            let root_el = document.createElement('div');
            // data chart
            let canvas = document.createElement('canvas');
            canvas.id = `id_chart_${subset['pk']}`;
            canvas.width = "400";
            canvas.height = "300";
            root_el.appendChild(canvas);

            // fixed properties
            if ('fixed properties' in subset) {
              let fix_h = document.createElement('h5');
              fix_h.innerHTML = "<strong>Fixed properties: </strong>";
              root_el.appendChild(fix_h);
              let fix_t = document.createElement('table');
              fix_t.className = "table table-sm";
              let fix = subset['fixed properties'];
              if (fix.length > 0) {
                let tr, th, td;
                    tr = document.createElement('tr');
                    for (let k of Object.keys(fix[0])) {
                      th = document.createElement('th');
                      th.innerHTML = `${k}`;
                      th.scope = "col";
                      tr.append(th);
                    }
                    fix_t.append(tr);
                    for (let b of fix) {
                      tr = document.createElement('tr');
                      for (let v of Object.values(b)) {
                        td = document.createElement('td');
                        td.innerHTML = `${v}`;
                        td.style = 'text-align:left';
                        tr.append(td);
                      }
                      fix_t.append(tr);
                    }
              } else {
                fix_t.innerHTML = "No fixed properties for this subset.";
              }
              root_el.appendChild(fix_t);
            }

            card_body.appendChild(root_el);
          }
          

          // additional files
          if (subset['additional files'].length !== 0) {
            let fs = subset['additional files'];
            let fs_h = document.createElement('h5');
            fs_h.innerHTML = "<strong>Additional files: </strong>";
            card_body.appendChild(fs_h);
            let fs_el = document.createElement('ul');
            for (let f of fs) {
              let f_el = document.createElement('li');
              f_el.innerHTML = `<a href="", target="_blank">${f['name']}</a>`;
              f_el.firstChild.href = f['path'];
              fs_el.appendChild(f_el);
            }
            card_body.appendChild(fs_el);
          }

          // reference
          if (Object.entries(subset['reference']).length !== 0) {
            let ref = subset['reference'];
            let ref_el = document.createElement('div');
            let ref_head = document.createElement('h5');
            ref_head.innerHTML = "<strong>Reference: </strong>";
            ref_el.appendChild(ref_head);
            let ref_body = document.createElement('p');
            for (let [key, author] of Object.entries(subset['authors'])) {
              ref_body.innerHTML += `${author['first_name'].split()[0]}.${author['last_name']},`
            }
            ref_body.innerHTML += `<i>${ref['title']}</i>, ${ref['journal']} `;
            ref_body.innerHTML += `<strong>${ref['vol']}</strong>, ${ref['pages_start']} `;
            if (ref['pages_end']) {
              ref_body.innerHTML += `&#8209;${ref['pages_end']} `;
            }
            ref_body.innerHTML += `${ref['year']}.`;
            if (ref['doi_isbn']) {
              ref_body.innerHTML += `doi:&nbsp;${ref['doi_isbn']}`;
            }
            ref_el.appendChild(ref_body);
            card_body.appendChild(ref_el);
          }

          card.appendChild(card_body);
          data_el.appendChild(card);
        }

        for (let element of document.getElementsByTagName('canvas')) {
          const plot_id = element.id;
          const plot_pk = plot_id.split('id_chart_')[1];
          axios
            .get('/materials/data-for-chart/' + plot_pk)
            .then(response => {
              if (Object.entries(response['data']['data']).length !== 0) {
                plot_data(plot_id, response['data']['data'],
                          response['data']['x title'],
                          response['data']['x unit'],
                          response['data']['y title'],
                          response['data']['y unit']);
              } else {
                element.style.display = "none";
              }
            });
        }
      });
    }
  });
}
