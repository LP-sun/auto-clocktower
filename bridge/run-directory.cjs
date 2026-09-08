const fs=require('node:fs'),path=require('node:path');
function createRunDirectory(base,mode,stamp=new Date().toISOString().replace(/[:.]/g,'-')){fs.mkdirSync(base,{recursive:true});return fs.mkdtempSync(path.join(base,`${mode}-${stamp}-`));}
module.exports={createRunDirectory};
