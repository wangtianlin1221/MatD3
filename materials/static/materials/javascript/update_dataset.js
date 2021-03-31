// Scripts related to updating a dataset
'use strict';

// Initialize axios
axios.defaults.xsrfCookieName = 'csrftoken';
axios.defaults.xsrfHeaderName = 'X-CSRFTOKEN';

// Messaging (for dynamic updates)
const create_message = (message_type, message) => {
  const flex = document.createElement('div');
  flex.classList.add('d-flex');
  const alert = document.createElement('div');
  alert.classList.add('alert', message_type);
  alert.innerHTML = message;
  flex.append(alert);
  document.getElementById('dynamic-messages').append(flex);
}

const delete_all_messages = () => {
  const messages = document.getElementById('dynamic-messages');
  while (messages.firstChild) {
    messages.firstChild.remove();
  }
}


// Helper function for building up part of the reference string
const authors_as_string = (authors) => {
  let authors_formatted = [];
  for (let author of authors) {
    authors_formatted.push(`${author.first_name[0]}. ${author.last_name}`);
  }
  return authors_formatted.join(', ');
}


// Extend any of the dropdown menus with a new entry
// (reference, material, property, ...)
function SelectEntryHandler(entry_type, label_name, post_url) {
  let card_id = 'new-' + entry_type + '-card';
  let form_id = entry_type + '-form';
  this.card = document.getElementById(card_id);
  this.form = document.getElementById(form_id);
  this.post_url = post_url;
  this.selectize_label_name = label_name;
  this.entry_type = entry_type;

  // Save new entry into the database and update selectize
  this.add_new_entry = () => {
    delete_all_messages();
    const form_data = new FormData(this.form);
    const label_name = this.selectize_label_name;
    axios
      .post(this.post_url, form_data)
      .then(response => {
        this.card.hidden = true;
        // Update all dropdowns of the current type
        for (let select_name in selectized) {
          if (select_name.includes(this.entry_type) || select_name.includes('space_group')) {
            if (this.entry_type === 'reference') {
              let article = response.data;
              let text =
                `${article.year} - ${authors_as_string(article.authors)}, ` +
                `${article.journal} ${article.vol}`;
              if (article.vol && article.pages_start) text += ',';
              text += ` ${article.pages_start} "${article.title}"`;
              form_data.set('text', text);
            }
            selectized[select_name][0].selectize.addOption({
              pk: response.data.pk, [label_name]: form_data.get(label_name),
            });
            selectized[select_name][0].selectize.refreshOptions;
            // selectized[select_name][0].selectize.setValue(response.data.pk, 0);
          }
        }
        // selectized[dispatcher_name][0].selectize.setValue(response.data.pk, 0);
        create_message(
          'alert-success',
          `New ${this.entry_type} "${form_data.get(label_name)}" ` +
          'successfully added to the database.');
        this.form.reset();
      }).catch(error => {
        create_message(
          'alert-danger',
          `Conflict: ${this.entry_type} "${form_data.get(label_name)}" ` +
          'already exists.');
        console.log(error.message);
        console.log(error.response.statusText);
      });
  }
  
  this.form.addEventListener('submit', event => {
    event.preventDefault();
    this.add_new_entry();
  });

  // The new entry field is shown/hidden with the '--add new--' (pk=0) field
  this.toggle_visibility = dispatcher_id => {
    $('#' + dispatcher_id).change(() => {
      if ($('#' + dispatcher_id).val() === '0') {
        this.card.hidden = false;
        window.scrollTo(0, 0);
      } else {
        this.card.hidden = true;
      }
    });
  }
}

const new_reference_handler =
  new SelectEntryHandler('reference', 'text', '/materials/references/');
const new_property_handler =
  new SelectEntryHandler('property', 'name', '/materials/properties/');
const new_unit_handler =
  new SelectEntryHandler('unit', 'label', '/materials/units/');
const new_space_group_handler = 
  new SelectEntryHandler('space-group', 'name', '/materials/space-groups/');

// All dropdown menus are filled asynchronously
var selectized = {};  // Must use 'var' here for Selenium
const selectize_wrapper = (name, data, initial_value, label_name) => {
  data.push({pk: 0, [label_name]: ' --add new--'});
  selectized[name] = $('#id_' + name).selectize({
    maxOptions: 500,
    valueField: 'pk',
    labelField: label_name,
    sortField: label_name,
    searchField: label_name,
    items: [initial_value],
    options: data,
  });
}

// Adding and removing authors on the new reference form
document
  .getElementById('add-more-authors-btn')
  .addEventListener('click', () => {
    const latest_first_name =
      document.getElementById('first-names').lastElementChild;
    const latest_last_name =
      document.getElementById('last-names').lastElementChild;
    const latest_institution =
      document.getElementById('institutions').lastElementChild;
    const first_name_copy = latest_first_name.cloneNode(true);
    const last_name_copy = latest_last_name.cloneNode(true);
    const institution_copy = latest_institution.cloneNode(true);
    first_name_copy.hidden = false;
    last_name_copy.hidden = false;
    institution_copy.hidden = false;
    const institution_input = institution_copy.getElementsByTagName('input')[0];
    let input_counter;
    if (latest_first_name.hasAttribute('name')) {
      input_counter =
        Number(latest_first_name.name.split('first-name-')[1]) + 1;
    } else {
      input_counter = 1;
    }
    first_name_copy.name = `first-name-${input_counter}`;
    last_name_copy.name = `last-name-${input_counter}`;
    institution_input.name = `institution-${input_counter}`;
    first_name_copy.id = `first-name-${input_counter}`;
    last_name_copy.id = `last-name-${input_counter}`;
    institution_copy.id = `institution-${input_counter}`;
    first_name_copy.value = '';
    last_name_copy.value = '';
    institution_input.value = '';
    institution_copy
      .getElementsByTagName('button')[0]
      .addEventListener('click', () => {
        first_name_copy.remove();
        last_name_copy.remove();
        institution_copy.remove();
      });
    document.getElementById('first-names').append(first_name_copy);
    document.getElementById('last-names').append(last_name_copy);
    document.getElementById('institutions').append(institution_copy);
  });
document
  .getElementById('add-more-authors-btn')
  .dispatchEvent(new Event('click'));


// Collapsable sections of the input
const toggle_section_visibility = (button_id, hidden_field_id, data_field_id) => {
  const hidden_field = document.getElementById(hidden_field_id);
  const button = document.getElementById(button_id);
  const data_field = document.getElementById(data_field_id);
  if (hidden_field.value === 'True') {
    $(data_field).toggle();
    $(button).css({'background': '#f3ebff'});
    $(button).html($(button).html().split('add)')[0] + 'remove)');
  }
  button.addEventListener('click', function() {
    $(data_field).toggle();
    if (hidden_field.value === 'True') {
      hidden_field.value = 'False';
      $(this).css({'background': '#dce9ff'});
      $(this).html($(this).html().split('remove)')[0] + 'add)');
    } else {
      hidden_field.value = 'True';
      $(this).css({'background': '#f3ebff'});
      $(this).html($(this).html().split('add)')[0] + 'remove)');
    }
  });
}


// Function that autofills the datapoints textarea
const autofill_data = (i_dataset, i_subset, copy_element, element) => {
  // let i_dataset, i_subset = element.id.split('import-data-file_')[1].split('_');
  const global_fill = i_subset == null;
  const form_data = new FormData();
  form_data.append('file', element.files[0]);
  if (!global_fill) {
    // Save the name of the original file for later use
    copy_element
      .querySelector(`#id_import_file_name_${i_dataset}_${i_subset}`)
      .value = element.files[0].name;
  }
  element.value = '';  // Clear the file list
  axios
    .post('/materials/autofill-input-data', form_data)
    .then(response => {
      const result =
        response.data.replace(/\n\r/g, '\n').replace(/\r/g, '\n'); // Windows
      const data = result.split(/&/);
      if (global_fill && data.length > 1) {
        const n_subsets = document.getElementById('id_number_of_subsets_' + i_dataset);
        for (let i = 1; i <= n_subsets.value; i++) {
          copy_element.querySelector('#id_datapoints_' + 'i_dataset_' + i).value =
            data[i-1].replace(/^\n/, '');
        }
      } else {
        if (i_subset) {
          copy_element.querySelector('#id_datapoints_' + i_dataset + '_' + i_subset).value = result;
        } else {
          copy_element.querySelector('#id_datapoints_' + i_dataset + '_1').value = result;
        }
      }
    })
    .catch(error => {
      if (!i_subset) i_subset = 1;
      copy_element.querySelector('#id_datapoints_' + i_dataset + '_' + i_subset).value = error;
    });
}


// Hide special property fields under subsets and show only normal input
function reset_subset_fields(subsets_all_element) {
  for (let input_type of ['atomic-structure-input', 'tolerance-factor-input']) {
    for (let element of subsets_all_element.getElementsByClassName(input_type)) {
      element.hidden = true;
    }
  }
  for (let element of subsets_all_element.getElementsByClassName('normal-input')) {
    element.hidden = false;
  }
  let elements =
    document.querySelectorAll('input[name^="lattice_constant_"]');
  for (let element of elements) {
    element.required = false;
  }
}


// Show atomic structure input fields; hide normal input fields and tolerance-factor input fields
const show_atomic_structure_fields = (subsets_all_element) => {
  $('#id_primary_property_1').change(function() {
    if ($('#id_primary_property_1').find(':selected').text() ===
      'atomic structure') {
      reset_subset_fields(subsets_all_element);
      for (let el of subsets_all_element.getElementsByClassName('atomic-structure-input')) {
        el.hidden = false;
      }
      for (let element of subsets_all_element.getElementsByClassName('normal-input')) {
        element.hidden = true;
      }
      // Make these fields required only if 'atomic structure' is the selected property
      for (let element of
        subsets_all_element.querySelectorAll('input[name^="lattice_constant_"]')) {
        element.required = true;
      }
    }
  });
}


// Show tolerance factor related parameters input fields; hide normal input fields and atomic structure fields
const show_tolerance_factor_fields = (subsets_all_element) => {
  $('#id_primary_property_1').change(function() {
    if ($('#id_primary_property_1').find(':selected').text() === 'tolerance factor related parameters') {
      reset_subset_fields(subsets_all_element);
      for (let el of subsets_all_element.getElementsByClassName('tolerance-factor-input')) {
        el.hidden = false;
        console.log(el.hidden);
        console.log(el);
      }
      for (let element of subsets_all_element.getElementsByClassName('normal-input')) {
        element.hidden = true;
      }
      for (let element of subsets_all_element.getElementsByClassName('atomic-structure-input')) {
        element.hidden = true;
      }
    }
  });
}


// Add suffix to elements in order to reuse the submit_data view function
let dataset = document.getElementsByClassName('dataset')[0];
let i_dataset = 1;
for (let element of dataset.querySelectorAll('input, textarea, select, button')) {
    element.id += '_' + i_dataset;
    element.name += '_' + i_dataset;
  }
  for (let element of dataset.getElementsByTagName('label')) {
    element.htmlFor += '_' + i_dataset;
  }
  for (let element of dataset.getElementsByClassName('collapse')) {
    element.id += '_' + i_dataset;
  }
  const subset = dataset.querySelector('#subsets_all')
  subset.id += '_' + i_dataset;

// primary property -selectize
axios
    .get('/materials/properties/')
    .then(response => {
      selectize_wrapper('primary_property_1', response.data, initial_primary_property, 'name');
      document.getElementById('id_primary_property_1').dispatchEvent(new Event('change'));
      new_property_handler.toggle_visibility('id_primary_property_1');
    });

// space group -selectize
axios
    .get('/materials/space-groups/')
    .then(response => {
      selectize_wrapper('space_group_1', response.data, initial_space_group, 'name');
      document.getElementById('id_' + 'space_group_' + i_dataset).dispatchEvent(new Event('change'));
      new_space_group_handler.toggle_visibility('id_' + 'space_group_' + i_dataset);
    });

// Add/remove synthesis methods
toggle_section_visibility(
  'synthesis-button_' + i_dataset,
  'id_with_synthesis_details_' + i_dataset,
  'synthesis-body_' + i_dataset);
// Add/remove experimental details
toggle_section_visibility(
  'experimental-button_' + i_dataset,
  'id_with_experimental_details_' + i_dataset,
  'experimental-body_' + i_dataset);
//Add/remove computational details
toggle_section_visibility(
  'computational-button_' + i_dataset,
  'id_with_computational_details_' + i_dataset,
  'computational-body_' + i_dataset);


// Function that appends a subset template
let counter_fixed = 0;
let counter_bond_length = 0;
const add_subset = (i_dataset, i_subset) => {
  // Append element's id and name with _${i_dataset}_${i_subset} suffix
  const copy =
    document.getElementsByClassName('subset-template')[0].cloneNode(true);
  copy.classList.remove('d-none', 'subset-template');
  copy.getElementsByClassName('card-header')[0].innerHTML =
    'Subset #' + i_subset;
  const suffix = '_' + i_dataset + '_' + i_subset;
  for (let element of copy.querySelectorAll('input, textarea, select, button')) {
    // Set the defaults of radio buttons from the first subset
    // if (i_subset > 1 && element.type === 'radio') {
    //   const el = document.getElementById(element.id + '_' + 1);
    //   element.checked = el.checked;
    // }
    element.id += suffix;
    element.name += suffix;
  }
  for (let element of copy.getElementsByTagName('label')) {
    element.htmlFor += suffix;
  }
  for (let element of copy.getElementsByClassName('collapse')) {
    element.id += suffix;
  }
  const legend = copy.querySelector('#legends_all')
  legend.id += '_' + i_dataset + '_' + i_subset;
  // Fill datapoints textarea with data from imported file
  copy
    .getElementsByClassName('import-data-file')[0]
    .addEventListener('change', function() {
      autofill_data(i_dataset, i_subset, copy, this);
    });

  // Add fixed properties
  copy.getElementsByClassName('fixed-properties')[0].id =
    'fixed-properties_' + i_dataset + '_' + i_subset;
  const fixed_prop_btn = copy.getElementsByClassName('add-fixed-property')[0]
  // fixed_prop_btn.id = 'add-fixed-property_' + i_dataset + '_' + i_subset;
  fixed_prop_btn.addEventListener('click', function() {
    add_fixed_property(i_dataset, i_subset, ++counter_fixed);
  });

  // Fill atomic structure data from imported file
  copy
    .getElementsByClassName('import-lattice-parameters')[0]
    .addEventListener('change', function() {
      import_lattice_parameters(i_dataset, i_subset, copy, this);
    });
  
  // Enable/ Disable spin_state field
  const toggle_field_status = (copy_el, element_label) => {
    let input_el = copy_el.querySelector('#id_element_' + element_label + suffix);
    let select_el = copy_el.querySelector('#id_spin_state_' + element_label + suffix);
    input_el.addEventListener('change', function() {
      if (['Fe', 'Co', 'Ni'].includes(input_el.value)) {
        select_el.disabled = false;
      } else {
        select_el.disabled = true;
      }
    });
    input_el.dispatchEvent(new Event('change'));
  }
  
  toggle_field_status(copy, 'I');
  toggle_field_status(copy, 'II');
  toggle_field_status(copy, 'IV');
  toggle_field_status(copy, 'X');

  
  // Select or add a reference
  let reference_name = 'select_reference_' + i_dataset + '_' + i_subset;
  if (initial_reference.length < i_dataset || initial_reference[i_dataset-1].length < i_subset) {
    // console.log("initial is empty.");
    axios
      .get('/materials/references/', {
        transformResponse: [function(data) {
          // Transform each article object into a string
          let articles = JSON.parse(data);
          for (let article of articles) {
            article.text =
              `${article.year} - ${authors_as_string(article.authors)}, ` +
              `${article.journal} ${article.vol}`;
            if (article.vol && article.pages_start) article.text += ',';
            article.text += ` ${article.pages_start} "${article.title}"`;
          }
          return articles;
        }],
      })
      .then(response => {
        selectize_wrapper(reference_name, response.data, '', 'text');
        new_reference_handler.toggle_visibility('id_' + reference_name);
      });
  } else {
    // console.log("not empty:", initial_reference[i_dataset-1][i_subset-1]);
    axios
      .get('/materials/references/', {
        transformResponse: [function(data) {
          // Transform each article object into a string
          let articles = JSON.parse(data);
          for (let article of articles) {
            article.text =
              `${article.year} - ${authors_as_string(article.authors)}, ` +
              `${article.journal} ${article.vol}`;
            if (article.vol && article.pages_start) article.text += ',';
            article.text += ` ${article.pages_start} "${article.title}"`;
          }
          return articles;
        }],
      })
      .then(response => {
        selectize_wrapper(reference_name, response.data, initial_reference[i_dataset-1][i_subset-1], 'text');
        new_reference_handler.toggle_visibility('id_' + reference_name);
      });
  }
  
    
  document.getElementById('subsets_all_' + i_dataset).append(copy);

  // Add legends
  const number_of_curves = document.querySelector('#id_number_of_curves_' + i_dataset + '_' + i_subset);  
  number_of_curves.addEventListener('change', function() {
    const n_curve_current = legend.children.length;
    const n_curve_requested = this.value;
    const n_to_add = n_curve_requested - n_curve_current;
    if (n_to_add > 0) {
      for (let i = 1; i <= n_to_add; i++) {
        add_legend(i_dataset, i_subset, n_curve_current+i);
      }
    }
    if (n_to_add < 0) {
      for (let i = n_to_add; i < 0; i++) {
        legend.lastChild.remove();
      }
    }
  });
  number_of_curves.dispatchEvent(new Event('change'));
}


// Function that adds a legend template
const add_legend = (i_dataset, i_subset, i_curve) => {
  const copy =
    document.getElementsByClassName('legend-template')[0].cloneNode(true);
  copy.classList.remove('d-none', 'legend-template');
  copy.getElementsByClassName('input-group-text')[0].innerHTML =
    'Curve #' + i_curve;
  const suffix = '_' + i_dataset + '_' + i_subset + '_' + i_curve;
  for (let element of copy.querySelectorAll('input, textarea, select')) {
    element.id += suffix;
    element.name += suffix;
  }
  document.getElementById('legends_all_' + i_dataset + '_' + i_subset).append(copy);
}


// Function that creates a new set of fixed property fields
const add_fixed_property = (i_dataset, i_subset, counter, prop_initial='', unit_initial='', sign_initial='', value_initial='') => {
    const copy = document.getElementsByClassName('fixed-property-template')[0]
                         .cloneNode(true);
    const suffix = i_dataset + '_' + i_subset + '_' + counter;
    let el, name;
    copy.classList.remove('d-none', 'fixed-property-template');
    const edit_id_and_name = type => {
      name = 'fixed_' + type + '_' + suffix;
      el = copy.querySelector('[name="fixed_' + type + '"]');
      el.id = 'id_' + name;
      el.name = name;
    }
    edit_id_and_name('property');
    const property_name = name;
    axios.get('/materials/properties/').then(response => {
      selectize_wrapper(property_name, response.data, prop_initial, 'name');
      new_property_handler.toggle_visibility('id_' + property_name);
    });
    edit_id_and_name('unit');
    const unit_name = name;
    axios.get('/materials/units/').then(response => {
      selectize_wrapper(unit_name, response.data, unit_initial, 'label');
      new_unit_handler.toggle_visibility('id_' + unit_name);
    });
    edit_id_and_name('sign');
    if (sign_initial) {
      copy.querySelector('[name="fixed_sign_' + suffix + '"]').value = sign_initial;
    }
    edit_id_and_name('value');
    if (value_initial) {
      copy.querySelector('[name="fixed_value_' + suffix + '"]').value = value_initial;
    }
    // Remove a fixed property
    copy
      .getElementsByClassName('close-fixed-property')[0]
      .addEventListener('click', function() {
        let row = this.parentNode.parentNode.parentNode.parentNode;
        row.remove();
      });
    document.getElementById('fixed-properties_' + i_dataset + '_' + i_subset).append(copy);
}


// Autofill lattice parameters and coordinates from uploaded file
const import_lattice_parameters = (i_dataset, i_subset, copy_element, element) => {
  // let i_subset = element.id.split('import-lattice-parameters_')[1];
  const form_data = new FormData();
  form_data.append('file', element.files[0]);
  const is_cif_format = element.files[0].name.match(/\.cif$/) !== null;
  if (i_subset) {
    // Save the name of the original file for later use
    copy_element
      .querySelector(`#id_import_file_name_atomic_${i_dataset}_${i_subset}`)
      .value = element.files[0].name;
  }
  element.value = '';  // Clear the file list
  axios
    .post('/materials/autofill-input-data', form_data)
    .then(response => {
      let data = response.data;
      let a, b, c, alpha, beta, gamma;
      const process_batch = (input_data, dest_suffix) => {
        const lines = input_data.split('\n');
        let aims_format = false;
        if (!is_cif_format) {
          for (let line of lines) {
            if (line.match(/^ *lattice_vector/)) {
              aims_format = true;
              break;
            }
          }
        }
        const i_subset_loc = i_subset ? i_subset : '1';
        const geometry_format =
          copy_element.querySelector(`#id_geometry_format_${i_dataset}_${i_subset_loc}`);
        if (aims_format) {
          // Generate the atomic structure (lattice constants and angles)
          // from lattice vectors
          geometry_format.value = 'aims';
          let lattice_vectors = [];
          const regex =
            /^ *lattice_vector\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\b/;
          let match_;
          for (let line of lines) {
            match_ = line.match(regex);
            if (match_) {
              lattice_vectors.push([match_[1], match_[2], match_[3]]);
            }
            if (lattice_vectors.length == 3) break;
          }
          const norm = vector =>
            Math.sqrt(Math.pow(vector[0],2) +
                      Math.pow(vector[1],2) +
                      Math.pow(vector[2],2));
          const get_angle = (v1, v2, norm1, norm2) =>
            Math.acos((v1[0]*v2[0]+v1[1]*v2[1]+v1[2]*v2[2])/norm1/norm2)*360/2/Math.PI;
          if (lattice_vectors.length < 3) {
            throw 'Unable to find three lattice vectors';
          }
          a = norm(lattice_vectors[0]);
          b = norm(lattice_vectors[1]);
          c = norm(lattice_vectors[2]);
          alpha = get_angle(lattice_vectors[1], lattice_vectors[2], b, c);
          beta = get_angle(lattice_vectors[0], lattice_vectors[2], a, c);
          gamma = get_angle(lattice_vectors[0], lattice_vectors[1], a, b);
        } else if (is_cif_format) {
          geometry_format.value = 'cif';
          let match_;
          let matches = {};
          for (let line of lines) {
            match_ = line.match(
              /^_cell_(?:length|angle)_([a-c]|alpha|beta|gamma) +(.*)/);
            if (match_) matches[match_[1]] = match_[2];
            if ('gamma' in matches && 'beta' in matches && 'alpha' in matches &&
                'c' in matches && 'b' in matches && 'a' in matches) break;
          }
          a = matches['a'];
          b = matches['b'];
          c = matches['c'];
          alpha = matches['alpha'];
          beta = matches['beta'];
          gamma = matches['gamma'];
        } else {
          // Read the atomic structure directly from an input file
          const nr_reg =
            /\b([a-z]+)\s+(-?(?:\d+(?:\.\d+)?|\.\d+)(?:\(\d+(?:\.\d+)?\)|\b))/g;
          let matches = [];
          while (matches = nr_reg.exec(input_data)) {
            switch(matches[1]) {
              case 'a':     a     = matches[2]; break;
              case 'b':     b     = matches[2]; break;
              case 'c':     c     = matches[2]; break;
              case 'alpha': alpha = matches[2]; break;
              case 'beta':  beta  = matches[2]; break;
              case 'gamma': gamma = matches[2]; break;
            }
          }
          if (a && b && c && alpha && beta && gamma) {
            input_data = '';
          } else {
            a = b = c = alpha = beta = gamma = '';
          }
        }
        const set_value = (part_id, value) => {
          copy_element.querySelector(part_id + dest_suffix).value = value;
        }
        set_value('#id_lattice_constant_a_', a);
        set_value('#id_lattice_constant_b_', b);
        set_value('#id_lattice_constant_c_', c);
        set_value('#id_lattice_constant_alpha_', alpha);
        set_value('#id_lattice_constant_beta_', beta);
        set_value('#id_lattice_constant_gamma_', gamma);
        set_value('#id_atomic_coordinates_', input_data);
      }
      try {
        if (i_subset) {
          process_batch(data, i_dataset + '_' + i_subset);
        } else {
          data = data.replace(/\n\r/g, '\n').replace(/\r/g, '\n'); // Windows
          const subsets = data.split('&');
          for (let i = 0; i < subsets.length; i++) {
            if (subsets[i]) {
              process_batch(subsets[i].replace(/^\n/, ''), `${i_dataset}_${i+1}`);
            }
          }
        }
      } catch(error) {
        copy_element.querySelector('#id_atomic_coordinates_' + i_dataset + '_' + i_subset).value = error;
      }
    }).
     catch(error => {
       if (!i_subset) i_subset = 1;
       copy_element
         .querySelector('#id_atomic_coordinates_' + i_dataset + '_' + i_subset).innerHTML = error;
     });
}


// Add a new subset to the dataset
const number_of_subsets = document.getElementById('id_number_of_subsets_' + i_dataset);
let all_subsets = document.getElementById('subsets_all_' + i_dataset);
number_of_subsets.addEventListener('change', function() {
  const n_subset_current = subset.children.length;
  const n_subset_requested = this.value;
  const n_to_add = n_subset_requested - n_subset_current;
  if (n_to_add > 0) {
    for (let i = 1; i <= n_to_add; i++) {
      add_subset(i_dataset, n_subset_current+i);
      $('#id_primary_property_' + i_dataset).change();
    }
  }
  if (n_to_add < 0) {
    for (let i = n_to_add; i < 0; i++) {
      subset.lastChild.remove();
    }
  }
});
number_of_subsets.dispatchEvent(new Event('change'));

show_atomic_structure_fields(all_subsets, i_dataset);
show_tolerance_factor_fields(all_subsets, i_dataset);

$('#id_primary_property_' + i_dataset).change(function() {
  const selected = $('#id_primary_property_' + i_dataset).find(':selected').text();
  if (selected !== 'atomic structure' && selected !== 'tolerance factor related parameters') {
    reset_subset_fields(all_subsets, i_dataset);
  }
});
